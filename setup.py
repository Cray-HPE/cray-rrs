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
from setuptools import setup, find_packages

with open("LICENSE") as license_file:
    LICENSE = license_file.read()
with open("requirements.txt") as reqs_file:
    REQUIRMENTS = reqs_file.readlines()[1:]
with open(".docker_version") as vers_file:
    DOCKER_VERSION = vers_file.read().strip()
with open(".chart_version") as vers_file:
    CHART_VERSION = vers_file.read().strip()
setup(
    name="rrs",
    author="HPE",
    author_email="sravani.sanigepalli@hpe.com,ravikanth.nalla@hpe.com,arka.pramanik@hpe.com,keshav.varshney@hpe.com",
    url="http://hpe.com",
    description="RRS (Rack Resiliency Service)",
    long_description="RRS (Rack Resiliency Service)",
    version=DOCKER_VERSION,
    package_data={"": ["../api/openapi.yaml"]},
    packages=find_packages(),
    license=LICENSE,
    include_package_data=True,
    install_requires=REQUIRMENTS,
)
