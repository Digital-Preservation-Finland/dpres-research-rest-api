dpres-research-rest-api - REST API for metadata validation and triggering SIP creation
======================================================================================


This web application provides a REST API that allows user to trigger dataset validation/preservation using packaging service. The web application must be installed on same server as the packaging service.


Installation
------------

RPM package can be installed from dpres-rpms.csc.fi::

   yum install dpres-research-rest-api

Installation from git::
   pip install -r requirements_dev.txt
   make install

By default REST API listens to port 80. This can be changed by configuring
apache configuration file: /etc/httpd/conf.d/dpres-research-rest-api-httpd.conf

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

<validation result> is ``true`` if dataset metadata is valid, and ``false`` is metadata is invalid or missing. The <error_message> is empty if dataset metadata is valid.


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

	OR

	run the mockup which just returns always 200:

	cd tests/mockup_api
	FLASK_APP=mockup.py python -mflask run --port=5001 --host=0.0.0.0
