from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

setup(
    name='zerohub',
    version='1.0',
    description='Zero-Hub Client',
    long_description='Zero-Hub Client',
    url='https://github.com/zero-os/0-hub',
    author='Maxime Daniel',
    author_email='maxime@gig.tech',
    license='Apache 2.0',
    packages=find_packages(),
    include_package_data=True,
    namespace_packages=['zeroos'],
    install_requires=['requests'],
)
