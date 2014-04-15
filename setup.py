import os
import pip
import sys

from setuptools.command.test import test as TestCommand
from pip.req import parse_requirements
from versioning import get_version

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

def requirements():
    return [str(ir.req) for ir in parse_requirements('requirements.txt')]

readme = open('README.rst').read()

setup(
    name='sleepwalker',
    version=get_version(),
    description="sleepwalker - Interact with REST-servers using reschema-based schemas",
    long_description=readme,
    author="Riverbed Technology",
    author_email="cwhite@riverbed.com",
    packages=[
        'sleepwalker',
    ],
    package_dir={'sleepwalker': 'sleepwalker'},
    scripts=[
    ],
    include_package_data=True,
    install_requires=requirements(),
    keywords='sleepwalker',
    tests_require=['pytest', 'mock'],
)
