dpres-research-rest-api - REST API for metadata validation and triggering SIP creation
======================================================================================


This web application provides a REST API that allows:

1. users to validate the files and related metadata in IDA
2. Trigger a SIP creation process

Usage
-------------------
To run this you need to have standard Python tools installed (e.g. pip).

1. Enable virtualenv, before any of steps below::

	virtualenv venv
	source venv/bin/activate
	pip install --upgrade pip setuptools

2. Install requirements in virtualenv::

	pip install -r requirements_dev.txt

3. Run the REST API::

	FLASK_APP=run.py python -mflask run

Usage on Pouta test server
-------------------

Prerequisites:

Apache, Shibboleth, Ansible, mod_wsgi and mod_ssl have to be installed::

        sudo yum install ansible
        sudo yum install httpd
        sudo yum install shibboleth
        sudo yum install mod_wsgi
        sudo yum install mod_ssl

Installation:

Install ansible playbook::

        git clone https://source.csc.fi/scm/git/pas/ansible-dpres-admin-apache
        cd ansible-dpres-admin-apache/
        sudo ansible-playbook -i "localhost," -c local dpres-rest-api.yml

Install dpres-research-rest-api::

        git clone https://source.csc.fi/scm/git/pas/dpres-research-rest-api
        cd dpres-research-rest-api/
        git checkout develop
        sudo pip install -r requirements_dev.txt
        sudo make install


Updating source files:

To update changes in dpres-research-rest-api::

        git pull
        sudo rm -r /usr/lib/python2.7/site-packages/research_rest_api/
        sudo make install
        sudo apachectl restart

Start, stop and restart apache server::
        sudo apachectl start
        sudo apachectl stop
        sudo apachectl restart
