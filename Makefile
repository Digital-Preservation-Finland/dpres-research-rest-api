PREFIX=/usr
ROOT=
PYROOT=${ROOT}/
ETC=${ROOT}/etc
SHAREDIR=${ROOT}${PREFIX}/share/dpres-research-rest-api

APACHE_CONF_DIR=${ETC}/httpd/conf.d
APACHE_CONF_FILE=${APACHE_CONF_DIR}/dpres-research-rest-api-httpd.conf

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

	mkdir -p "${APACHE_CONF_DIR}"

	# Copy configuration file
	cp include/etc/httpd/conf.d/* "${APACHE_CONF_DIR}/"
	chmod 644 ${APACHE_CONF_FILE}

	# Install web app using Python setuptools
	python setup.py build ; python ./setup.py install -O1 --prefix="${PREFIX}" --root="${PYROOT}" --record=INSTALLED_FILES.in
	cat INSTALLED_FILES.in | sed 's/^/\//g' >> INSTALLED_FILES
	echo "-- INSTALLED_FILES"
	cat INSTALLED_FILES
	echo "--"

test:
	py.test -svvvv --full-trace --junitprefix=dpres-research-rest-api --junitxml=junit.xml tests

docs:
	make -C doc html
	make -C doc pdf

docserver:
	make -C doc docserver

killdocserver:
	make -C doc killdocserver

coverage:
	py.test tests --cov=research_rest_api --cov-report=html
	coverage report -m
	coverage html
	coverage xml

clean: clean-rpm
	find . -iname '*.pyc' -type f -delete
	find . -iname '__pycache__' -exec rm -rf '{}' \; | true
	rm coverage.xml
	rm -r htmlcov
	rm junit.xml

clean-rpm:
	rm -rf rpmbuild

rpm-sources:
	create-archive.sh
	preprocess-spec-m4-macros.sh include/rhel7

rpm: rpm-sources
	build-rpm.sh
