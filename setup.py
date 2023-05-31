"""Installation script for the 'dpres-research-rest-api' package"""

import sys

from setuptools import setup, find_packages
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
        setup_requires=['setuptools_scm'],
        use_scm_version=True,
        install_requires=[
            "flask",
            "flask-cors",
        ],
        tests_require=['pytest'],
        cmdclass={'test': PyTest}
    )


if __name__ == '__main__':
    main()
