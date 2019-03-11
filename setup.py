"""Installation script for the 'dpres-research-rest-api' package"""

import sys

from setuptools import setup, find_packages
from version import get_version
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):

    """Test to storage package"""
    test_args = None
    test_suite = True

    def finalize_options(self):
        """Add options for pytest test runner"""

        TestCommand.finalize_options(self)
        self.test_args = ['--verbose']
        self.test_suite = True

    def run_tests(self):
        """ Do the tests"""

        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


def main():
    """Install dpres-research-rest-api Python libraries"""
    setup(
        name='dpres-research-rest-api',
        packages=find_packages(exclude=['tests', 'tests.*']),
        install_requires=[
            "flask",
            "flask-cors",
            "metax_access@git+https://gitlab.csc.fi/dpres/"
            "metax-access.git@develop",
            "siptools_research@git+https://gitlab.csc.fi/dpres/"
            "dpres-siptools-research.git@develop",
            "upload_rest_api@git+https://gitlab.csc.fi/dpres/"
            "upload-rest-api.git@develop"
        ],
        tests_require=['pytest'],
        cmdclass={'test': PyTest},
        version=get_version())


if __name__ == '__main__':
    main()
