PREFIX = /usr
ROOT =
PYROOT = ${ROOT}/
ETC = ${ROOT}/etc
SHAREDIR = ${ROOT}${PREFIX}/share/dpres-research-rest-api

PYTHON ?= python3

all: info

info:
	@echo
	@echo "PAS dpres-research-rest-api for locationdb"
	@echo
	@echo "Usage:"
	@echo "  make test 			- Run all unit tests"
	@echo "  make install		- Install dpres-research-rest-api"
	@echo

install:
	# Cleanup temporary files
	rm -f INSTALLED_FILES
	rm -f INSTALLED_FILES.in

	# Install web app using Python setuptools
	python setup.py build ; python ./setup.py install -O1 --prefix="${PREFIX}" --root="${PYROOT}" --record=INSTALLED_FILES.in
	cat INSTALLED_FILES.in | sed 's/^/\//g' >> INSTALLED_FILES
	echo "-- INSTALLED_FILES"
	cat INSTALLED_FILES
	echo "--"

install3:
	# Cleanup temporary files
	rm -f INSTALLED_FILES
	rm -f INSTALLED_FILES.in

	# Install web app using Python setuptools
	python3 setup.py build ; python3 ./setup.py install -O1 --prefix="${PREFIX}" --root="${PYROOT}" --record=INSTALLED_FILES.in
	cat INSTALLED_FILES.in | sed 's/^/\//g' >> INSTALLED_FILES
	echo "-- INSTALLED_FILES"
	cat INSTALLED_FILES
	echo "--"

test:
	${PYTHON} -m pytest tests/app_test.py \
	    -svvvv --full-trace \
	    --junitprefix=dpres-research-rest-api --junitxml=junit.xml

.e2e/ansible-fairdata:
	git clone https://gitlab.ci.csc.fi/dpres/ansible-fairdata-pas.git .e2e/ansible-fairdata

.e2e/ansible-fetch-fairdata: .e2e/ansible-fairdata
	cd .e2e/ansible-fairdata && \
		git fetch --all && \
		git checkout $(FAIRDATA_ANSIBLE_BRANCH) && \
		git reset --hard origin/$(FAIRDATA_ANSIBLE_BRANCH) && \
		git clean -fdx && \
		git status

e2e-localhost-provision-fairdata: .e2e/ansible-fetch-fairdata
	cd .e2e/ansible-fairdata ; ansible-galaxy install -r requirements.yml --force ; ansible-playbook -i inventory/e2e-test site.yml -e '{"rpm_repos_pouta": [${RPM_REPOS}]}'

e2e-distributed-provision-fairdata: .e2e/ansible-fetch-fairdata
	cd .e2e/ansible-fairdata ; ansible-galaxy install -r requirements.yml --force ; ansible-playbook -i inventory/e2e-test site.yml -e '{"rpm_repos_pouta": [${RPM_REPOS}], "dp_host": "fairdata-pas-instance"}'

.e2e/ansible-preservation:
	git clone https://gitlab.ci.csc.fi/dpres/ansible-preservation-system.git .e2e/ansible-preservation

.e2e/ansible-fetch-preservation: .e2e/ansible-preservation
	cd .e2e/ansible-preservation && \
		git fetch --all && \
		git checkout $(PRESERVATION_ANSIBLE_BRANCH) && \
		git reset --hard origin/$(PRESERVATION_ANSIBLE_BRANCH) && \
		git clean -fdx && \
		git status && \
		if [ -f requirements.yml ]; then \
			ansible-galaxy install -r requirements.yml --force; \
		fi

e2e-localhost-cleanup: .e2e/ansible-fetch-preservation
	cd .e2e/ansible-preservation ; ansible-playbook -i inventory/localhost external_roles/test-cleanup/cleanup.yml

e2e-distributed-cleanup: .e2e/ansible-fetch-preservation
	cd .e2e/ansible-preservation ; ansible-playbook -i inventory/pouta-fairdata-pas external_roles/test-cleanup/cleanup.yml

e2e-localhost-provision-preservation: .e2e/ansible-fetch-preservation
	cd .e2e/ansible-preservation ; ansible-galaxy install -r requirements.yml --force ; ansible-playbook -i inventory/localhost testing-site.yml -e '{"rpm_repos_pouta": [${RPM_REPOS}]}'

e2e-distributed-provision-preservation: .e2e/ansible-fetch-preservation
	cd .e2e/ansible-preservation ; ansible-galaxy install -r requirements.yml --force ; ansible-playbook -i inventory/pouta-fairdata-pas testing-site.yml -e '{"rpm_repos_pouta": [${RPM_REPOS}]}'

e2e-test:
	pytest-3 -svvv --junitprefix=dpres-research-rest-api --junitxml=junit.xml tests/e2e

e2e-localhost-provision: e2e-localhost-provision-preservation e2e-localhost-provision-fairdata

e2e-distributed-provision: e2e-distributed-provision-preservation e2e-distributed-provision-fairdata

e2e-localhost: e2e-localhost-cleanup e2e-localhost-provision e2e-test

e2e-distributed: e2e-distributed-cleanup e2e-localhost-cleanup e2e-distributed-provision e2e-test

docs:
	make -C doc html
	make -C doc pdf

docserver:
	make -C doc docserver

killdocserver:
	make -C doc killdocserver

coverage:
	${PYTHON} -m pytest tests --cov=research_rest_api --cov-report=html
	coverage report -m
	coverage html
	coverage xml

clean: clean-rpm
	find . -iname '*.pyc' -type f -delete
	find . -iname '__pycache__' -exec rm -rf '{}' \; | true
	rm -f coverage.xml
	rm -rf htmlcov
	rm -f junit.xml

clean-rpm:
	rm -rf rpmbuild

rpm-sources:
	create-archive.sh
	preprocess-spec-m4-macros.sh include/rhel7

rpm: rpm-sources
	build-rpm.sh
