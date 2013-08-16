try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

from sleepwalker.version import get_git_version

setup(name="sleepwalker",
      version=get_git_version(),
      description="sleepwalker - Interact with REST-servers using reschema-based schemas",
      author="Riverbed Technology",
      author_email="cwhite@riverbed.com",
      
      packages = find_packages(),
      scripts = [
        ],
      install_requires = [
          ],
      include_package_data = True)
