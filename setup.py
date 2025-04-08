from setuptools import setup, find_packages

with open("LICENSE") as license_file:
    LICENSE = license_file.read()

with open("requirements.txt") as reqs_file:
    REQUIRMENTS = reqs_file.readlines()[1:]

with open(".version") as vers_file:
    VERSION = vers_file.read().strip()

setup(
    name="rrs",
    author="Cray Inc.",
    author_email="arka.pramanik@hpe.com, keshav.varshney@hpe.com",
    url="http://hpe.com",
    description="RRS Rack Resiliency Service",
    long_description="RRS Rack Resiliency Service",
    version=VERSION,
    package_data={"": ["../api/openapi.yaml"]},
    packages=find_packages(),
    license=LICENSE,
    include_package_data=True,
    install_requires=REQUIRMENTS,
)
