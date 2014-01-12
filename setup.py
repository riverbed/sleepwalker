import os
import pip
import sys

from setuptools.command.test import test as TestCommand
from pip.req import parse_requirements

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

def requirements():
    return [str(ir.req) for ir in parse_requirements('requirements.txt')]
    
def get_version():
    try:
        # pip-installed packages can get the version from the 'version.txt'
        # file, since it is included in the package MANIFEST.
        with open('version.txt', 'r') as f:
            return f.read().strip()
    except IOError:
        # since 'version.txt' is .gitignored, running setup.py (install|develop)
        # from a git repo requires a bit of bootstrapping. in this case, we use
        # the raw .git tag as the version.
        pip.main(['install', '-U',
                  '-i http://pypi.lab.nbttech.com/pq/development/', 'pq-ci'])
        from pq_ci import git
        tag = git.parse_tag()
        return '-'.join([tag['version'], tag['commits'], tag['sha']])

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
