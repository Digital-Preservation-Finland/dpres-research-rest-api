Packaging service REST API
==========================


This web application provides a REST API that allows user to trigger dataset validation/preservation using packaging service. The web application must be installed on same server as the packaging service.


Installation
------------

Clone this repository and install with pip::

   pip install --use-pep517 ../dpres-research-rest-api/

Configure apache to use WSGI application script file and restart apache.

Usage
-----

Dataset validation
^^^^^^^^^^^^^^^^^^
Validation is triggered with HTTP request::

   POST http://localhost/dataset/<dataset_id>/validate

The request returns message::

   HTTP/1.0 202 ACCEPTED
   Content-Type: application/json

   {
       "dataset_id": "<dataset_id>",
       "error": "<error_message>"
       "is_valid": <validation_result>
   }

<validation result> is ``true`` if dataset metadata is valid, and ``false`` if metadata is invalid or missing. The <error_message> is empty if dataset metadata is valid.


Dataset preservation
^^^^^^^^^^^^^^^^^^^^
Dataset packaging and preservation is triggered with request::

  POST http://localhost/dataset/<dataset_id>/preserve

The request returns message::

   HTTP/1.0 202 ACCEPTED
   Content-Type: application/json

   {
       "dataset_id": "<dataset_id>",
       "status": packaging
   }

The request is asyncronous and it does not provide information about success of packaging.


Testing
-------
To run this you need to have standard Python tools installed (e.g. pip).

1. Enable virtualenv, before any of steps below::

	virtualenv venv
	source venv/bin/activate
	pip install --upgrade pip setuptools

2. Install requirements in virtualenv::

	pip install -r requirements_dev.txt

3. Run the REST API::

	FLASK_APP=run.py python -mflask run

E2E testing
-----------
The E2E test in this repository does not test just the packaging REST API. It
is a E2E test for the whole Fairdata digital preservation service. The test
will install Digital Preservation System and Fairdata Digital Preservation
Service on localhost.

Access to Gitlab is required to set up e2e-test, so ensure that yout access token is installed::

        vim ~/.netrc

Install requirements::

        yum install ansible python36-pytest python2-pip

Alternatively, if you want to run test in virtual environment, install ansible
and pytest in virtual environment using pip. Ansible-preservation-system does
not work with newest ansible versions, but the version available on Centos 7
should work. The test will use pytest from executable `pytest-3`::

        pip install ansible==2.9.7 pytest
        ln -s $VIRTUAL_ENV/bin/pytest $VIRTUAL_ENV/bin/pytest-3

Choose RPM repositories to be used in test::

        export RPM_REPOS='"stable","master","develop"'

Choose the branch of ansible playbooks used for provisioning::

        export PRESERVATION_ANSIBLE_BRANCH=develop
        export FAIRDATA_ANSIBLE_BRANCH=develop

Run e2e test::

        make e2e-localhost

Troubleshooting
^^^^^^^^^^^^^^^
The test cleanup might remove git, which will cause test failure. When it
happens, simply reinstall git::

        yum install git

and try to run the tests again.



Copyright
---------
Copyright (C) 2019 CSC - IT Center for Science Ltd.

This program is free software: you can redistribute it and/or modify it under the terms
of the GNU Lesser General Public License as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along with
this program.  If not, see <https://www.gnu.org/licenses/>.
