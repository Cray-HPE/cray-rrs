#
# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#

NAME ?=cray-rrs
CHARTDIR ?= kubernetes
DOCKER_VERSION ?= $(shell head -1 .docker_version)
API_VERSION ?= $(shell head -1 .version)
CHART_VERSION ?= $(shell head -1 .chart_version)
STABLE ?= $(shell head -1 .stable)
IMAGE ?= artifactory.algol60.net/csm-docker/$(STABLE)/$(NAME)

RRS_API_CONTAINER_NAME ?= cray-rrs/cray-rrs-api
RRS_INIT_CONTAINER_NAME ?= cray-rrs/cray-rrs-init
RRS_WAIR_CONTAINER_NAME ?= cray-rrs/cray-rrs-wait
RRS_RMS_CONTAINER_NAME ?= cray-rrs/cray-rrs-rms

DOCKERFILE_API ?= Dockerfile.rrs.api
DOCKERFILE_INIT ?= Dockerfile.rrs.init
DOCKERFILE_WAIT ?= Dockerfile.rrs.wait
DOCKERFILE_RMS ?= Dockerfile.rrs.rms

CHART_METADATA_IMAGE ?= artifactory.algol60.net/csm-docker/stable/chart-metadata
HELM_IMAGE ?= artifactory.algol60.net/docker.io/alpine/helm:3.11.2
HELM_UNITTEST_IMAGE ?= artifactory.algol60.net/docker.io/quintush/helm-unittest:3.11.2-0.3.0
HELM_DOCS_IMAGE ?= artifactory.algol60.net/docker.io/jnorwood/helm-docs:v1.5.0
ifeq ($(shell uname -s),Darwin)
	HELM_CONFIG_HOME ?= $(HOME)/Library/Preferences/helm
else
	HELM_CONFIG_HOME ?= $(HOME)/.config/helm
endif
COMMA := ,

all: images chart

images : rrs_api_image rrs_init_image rrs_wait_image rrs_rms_image

rrs_api_image:
	docker buildx build --platform linux/amd64 --no-cache --pull ${DOCKER_ARGS} -f ${DOCKERFILE_API} --tag '${RRS_API_CONTAINER_NAME}:${DOCKER_VERSION}' .

rrs_init_image:
	docker buildx build --platform linux/amd64 --no-cache --pull ${DOCKER_ARGS} -f ${DOCKERFILE_INIT} --tag '${RRS_INIT_CONTAINER_NAME}:${DOCKER_VERSION}' .

rrs_wait_image:
	docker buildx build --platform linux/amd64 --no-cache --pull ${DOCKER_ARGS} -f ${DOCKERFILE_INIT} --tag '${RRS_WAIT_CONTAINER_NAME}:${DOCKER_VERSION}' .

rrs_rms_image:
	docker buildx build --platform linux/amd64 --no-cache --pull ${DOCKER_ARGS} -f ${DOCKERFILE_RMS} --tag '${RRS_RMS_CONTAINER_NAME}:${DOCKER_VERSION}' .

dev-image:
	docker buildx build --platform linux/amd64 --no-cache --pull ${DOCKER_ARGS} -f ${DOCKERFILE_API} --target dev --tag '${NAME}-dev:${DOCKER_VERSION}' .

# Replace Old String with New String in specified Target Files
#                        Old Regex          New String          Target file
replace_version_strings:
	./replace_strings.sh "0[.]0[.]0"        "$(API_VERSION)"    setup.py
	./replace_strings.sh "0[.]0[.]0-api"    "$(API_VERSION)"    src/api/openapi.yaml
	./replace_strings.sh "Unknown"          "$(API_VERSION)"    src/api/controllers/routes.py
	./replace_strings.sh "Unknown"          "$(API_VERSION)"    src/rrs/rms/rms.py
	./replace_strings.sh "0[.]0[.]0-chart"  "$(CHART_VERSION)"  kubernetes/cray-rrs/Chart.yaml
	./replace_strings.sh "0[.]0[.]0-docker" "$(DOCKER_VERSION)" kubernetes/cray-rrs/Chart.yaml
	./replace_strings.sh "S-T-A-B-L-E"      "$(STABLE)"         kubernetes/cray-rrs/values.yaml

lint: dev-image
	docker run --rm '${NAME}-dev:${DOCKER_VERSION}' /app/run_lint.sh

unittests: dev-image
	docker run --rm '${NAME}-dev:${DOCKER_VERSION}' /app/run_tests.sh

chart: chart-metadata chart-package chart-test

chart-metadata:
	docker run --rm \
		--user $(shell id -u):$(shell id -g) \
		-v ${PWD}/${CHARTDIR}/${NAME}:/chart \
		${CHART_METADATA_IMAGE} \
		--version "${CHART_VERSION}" --app-version "${DOCKER_VERSION}" \
		-i cray-rrs-api ${IMAGE}/cray-rrs-api:${DOCKER_VERSION} \
		-i cray-rrs-init ${IMAGE}/cray-rrs-init:${DOCKER_VERSION} \
		-i cray-rrs-wait ${IMAGE}/cray-rrs-wair:${DOCKER_VERSION} \
		-i cray-rrs-rms ${IMAGE}/cray-rrs-rms:${DOCKER_VERSION} \
		--cray-service-globals

helm:
	docker run --rm \
	    --user $(shell id -u):$(shell id -g) \
	    --mount type=bind,src="$(shell pwd)",dst=/src \
	    $(if $(wildcard $(HELM_CONFIG_HOME)/.),--mount type=bind$(COMMA)src=$(HELM_CONFIG_HOME)$(COMMA)dst=/tmp/.helm/config) \
	    -w /src \
	    -e HELM_CACHE_HOME=/src/.helm/cache \
	    -e HELM_CONFIG_HOME=/tmp/.helm/config \
	    -e HELM_DATA_HOME=/src/.helm/data \
	    $(HELM_IMAGE) \
	    $(CMD)

chart-package: packages/${NAME}-${CHART_VERSION}.tgz

packages/${NAME}-${CHART_VERSION}.tgz:
	CMD="dep up ${CHARTDIR}/${NAME}" $(MAKE) helm
	CMD="package ${CHARTDIR}/${NAME} -d packages" $(MAKE) helm

chart-test:
	CMD="lint ${CHARTDIR}/${NAME}" $(MAKE) helm
	docker run --rm -v ${PWD}/${CHARTDIR}:/apps ${HELM_UNITTEST_IMAGE} ${NAME}

chart-images: packages/${NAME}-${CHART_VERSION}.tgz
	{ CMD="template release $< --dry-run --replace --dependency-update" $(MAKE) -s helm; \
	  echo '---' ; \
	  CMD="show chart $<" $(MAKE) -s helm | docker run --rm -i $(YQ_IMAGE) e -N '.annotations."artifacthub.io/images"' - ; \
	} | docker run --rm -i $(YQ_IMAGE) e -N '.. | .image? | select(.)' - | sort -u

snyk:
	$(MAKE) -s chart-images | xargs --verbose -n 1 snyk container test

chart-gen-docs:
	docker run --rm \
	    --user $(shell id -u):$(shell id -g) \
	    --mount type=bind,src="$(shell pwd)",dst=/src \
	    -w /src \
	    $(HELM_DOCS_IMAGE) \
	    helm-docs --chart-search-root=$(CHARTDIR)

clean:
	$(RM) -r .helm packages
