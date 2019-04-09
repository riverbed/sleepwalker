# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

from gitpy_versioning import get_version

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

readme = open('README.rst').read()

doc = [
    'sphinx',
]
install_requires = [
        "requests",
        "uritemplate",
        "jsonpointer",
        "reschema>=0.4.11",
    ]
test = [
    'pytest',
    'mock',
    'requests_mock',
]
setup_requires = ['pytest-runner'] + install_requires

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
