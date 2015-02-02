from gitpy_versioning import get_version
from setuptools import setup

readme = open('README.rst').read()

doc = [
    'sphinx',
]

test = [
    'pytest',
    'mock',
    'requests_mock'
]

setup(
    name='sleepwalker',
    version=get_version(),
    description=("sleepwalker - Interact with REST-servers using "
                 "reschema-based schemas"),
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
    install_requires=[
        "requests",
        "uritemplate",
        "jsonpointer",
        "reschema",
    ],
    extras_require={
        'test': test,
        'doc': doc,
        'dev': test + doc,
        'all': [],
    },
    tests_require=test,
    keywords='sleepwalker',
    url="https://gitlab.lab.nbttech.com/steelscript/sleepwalker/",
)
