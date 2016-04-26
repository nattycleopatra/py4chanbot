#!/usr/bin/env python

from setuptools import setup

with open('LICENSE') as f:
    license = f.read()

setup(
        name='py4chanbot',
        version='0.1',
        description='4chan thread monitoring IRC bot',
        license=license,
        author='nattycleopatra',
        url='http://github.com/nattycleopatra/py4chanbot'
)
