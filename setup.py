# Copyright (c) 2019 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.
import sys
from setuptools import setup
from setuptools.command.test import test as TestCommand

from gitpy_versioning import get_version


class PyTest(TestCommand):
    user_options = [("pytest-args=", "a", "Arguments to pass to pytest")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ""

    def run_tests(self):
        import shlex

        # import here, cause outside the eggs aren't loaded
        import pytest

        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


readme = open('README.rst').read()

doc = [
    'sphinx',
]
install_requires = [
    "requests",
    "uritemplate",
    "jsonpointer",
    "reschema>=2.0",
]
test = [
    'pytest',
    'mock',
    'requests_mock',
]
setup_requires = ['pytest-runner']

setup(
    name='sleepwalker',
    version=get_version(),
    description=("sleepwalker - Interact with REST-servers using "
                 "reschema-based schemas"),
    long_description=readme,
    author="Riverbed Technology",
    author_email="eng-github@riverbed.com",
    packages=[
        'sleepwalker',
    ],
    package_dir={'sleepwalker': 'sleepwalker'},
    scripts=[
    ],
    include_package_data=True,

    install_requires=install_requires,
    extras_require={
        'test': test,
        'doc': doc,
        'dev': test + doc,
        'all': [],
    },
    tests_require=test,
    setup_requires=setup_requires,
    cmdclass={"pytest": PyTest},
    keywords='sleepwalker',
    url="http://pythonhosted.org/steelscript",
    license='MIT',
    platforms='Linux, Mac OS, Windows',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.5',
        'Topic :: System :: Networking',
    ],
    python_requires='>3.5.0',
)
