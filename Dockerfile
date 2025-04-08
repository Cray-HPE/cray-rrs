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
# Cray Rack Resiliency Service Dockerfile

# Base stage for shared dependencies
FROM alpine:3.21.3 AS base

WORKDIR /app
RUN mkdir -p /app /results
VOLUME ["/results"]

# Install dependencies
RUN apk add --upgrade --no-cache apk-tools && \
    apk update && \
    apk add --no-cache curl ca-certificates python3 py3-pip && \
    apk -U upgrade --no-cache && \
    update-ca-certificates

# Set up virtualenv and install app requirements
ADD requirements.txt constraints.txt /app/
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN python3 -m venv $VIRTUAL_ENV && \
    pip3 install --no-cache-dir -U pip -c constraints.txt && \
    pip3 install --no-cache-dir -U wheel -c constraints.txt && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ /app/src/

# -------- Stage for testing --------
FROM base AS testing

ADD docker_test_entry.sh /app/
ADD requirements-test.txt /app/
RUN pip3 install -r /app/requirements-test.txt
COPY tests /app/tests
ARG FORCE_TESTS=null
CMD ["./docker_test_entry.sh"]

# -------- Stage for code style checking --------
FROM testing AS codestyle

ADD .pylintrc .pycodestyle /app/
ADD runCodeStyleCheck.sh /app/
ARG FORCE_STYLE_CHECKS=null
CMD ["./runCodeStyleCheck.sh"]

# -------- Final image to run the Flask app --------
FROM base AS application

# Set Flask environment and app path
ENV FLASK_APP=src/server/app.py
ENV PYTHONPATH=/app/src

EXPOSE 80

# Final application entrypoint
CMD ["flask", "run", "--host=0.0.0.0", "--port=80"]

