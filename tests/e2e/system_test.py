"""Fairdata siptools workflow system test.

This is a e2e test for verifying the Fairdata digital preservation
system functionality. The test simulates the Management interface
(fddps-frontend) by using the API (admin-rest-api) to propose, generate
metadata, validate metadata, confirm and finally accept the dataset for
digital preservation. The test waits until the preservation_state of the
dataset will be changed to "In digital Preservation" (120). This means
that the created SIP has been accepted for digital preservation by the
digital preservation system.

The test dataset contains one HTML file and one TIFF file.

System environment setup
------------------------

IDA service is mocked. Metax is installed and deployed on the same
machine via ansible-fairdata-pas.
"""
import json
import logging
import pathlib
import subprocess

import pytest
import requests
from metax_access import (
    DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION,
    DS_STATE_GENERATING_METADATA,
    DS_STATE_IN_DIGITAL_PRESERVATION,
    DS_STATE_INITIALIZED,
    DS_STATE_METADATA_CONFIRMED,
    DS_STATE_REJECTED_IN_DIGITAL_PRESERVATION_SERVICE,
    DS_STATE_TECHNICAL_METADATA_GENERATED,
    DS_STATE_VALIDATING_METADATA,
)
from pymongo import MongoClient
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from tests.utils import wait_for
from upload_rest_api.config import CONFIG

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _get_admin_url():
    return json.loads(
        pathlib.Path("/usr/share/nginx/html/fddps-frontend/config.json").read_text("utf-8")
    )["apiUrl"]


ADMIN_API_URL = f"{_get_admin_url()}/secure/api/1.0"
REQUESTS_SESSION = requests.Session()
REQUESTS_SESSION.verify = False


def _get_passtate(dataset_identifier):
    response = requests.get(
        f'{ADMIN_API_URL}/datasets/{dataset_identifier}',
        verify=False
    )
    assert response.status_code == 200
    return response.json()['passtate']


MONGO_COLLECTIONS_TO_CLEAR = {
    "upload": "*",
    "eventdb": "*",
    "siptools-research": "*",
    "locationdb": ("aips", "files")
}

DIRS_TO_CLEAR = (
    "/var/spool/storage-rest-api/store-esp",
    "/var/spool/storage-rest-api/store-kova",
    "/var/spool/storage-rest-api/store-kova-full",
    "/var/spool/siptools_research/file_cache",
    "/var/spool/siptools_research/tmp",
    "/var/spool/siptools_research/workspaces",
    "/var/spool/preservation/local/dissemination",
    "/var/spool/preservation/local/ingest",
    "/var/spool/preservation/shared/dissemination",
    "/var/spool/preservation/shared/ingest",
    "/var/spool/upload/projects",
    "/var/spool/upload/tmp",
    "/home/fairdata/accepted",
    "/home/fairdata/approved",
    "/home/fairdata/disseminated",
    "/home/fairdata/rejected",
    "/home/fairdata/transfer",
    "/mnt/storage_vol01/glusterfs_pool01/storage_vol01/files",
)


DATA_CATALOG_PAS = "urn:nbn:fi:att:data-catalog-pas"


@pytest.fixture(scope="function", autouse=True)
def setup_e2e():
    """Cleanup procedure executed before each E2E test."""
    mongo_client = MongoClient(CONFIG["MONGO_HOST"], CONFIG["MONGO_PORT"])

    # Clear all applicable MongoDB collections. This does *not* remove
    # indexes, matching the pre-test state more closely.
    for db_name, collections in MONGO_COLLECTIONS_TO_CLEAR.items():
        mongo_db = getattr(mongo_client, db_name)

        if collections == "*":
            collections = mongo_db.list_collection_names()

        for col_name in collections:
            coll = getattr(mongo_db, col_name)
            coll.delete_many({})

    for path in DIRS_TO_CLEAR:
        subprocess.run(
            # `-mount` ensures other filesystems (eg. sshfs) are not
            # touched
            ["sudo", "find", path, "-mount", "-mindepth", "1", "-delete"],
            check=False
        )


def test_preservation_ida():
    """Test the preservation workflow using IDA."""
    dataset_identifier = "cr955e904-e3dd-4d7e-99f1-3fed446f96d5"

    try:
        logger.debug("Ensure that the dataset is initialized")
        response = REQUESTS_SESSION.get(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}'
        )
        assert _get_passtate(dataset_identifier) == DS_STATE_INITIALIZED

        logger.debug("Identify files")
        response = REQUESTS_SESSION.post(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}/generate-metadata',
        )
        assert response.status_code == 202
        assert _get_passtate(dataset_identifier) \
            == DS_STATE_GENERATING_METADATA

        logger.debug("Wait until metadata is generated")
        wait_for(
            lambda: _get_passtate(dataset_identifier)
            != DS_STATE_GENERATING_METADATA,
            timeout=300,
            interval=5
        )
        assert _get_passtate(dataset_identifier) \
            == DS_STATE_TECHNICAL_METADATA_GENERATED

        logger.debug("Propose dataset for preservation")
        response = REQUESTS_SESSION.post(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}/propose',
            data={'message': 'Foobar'}
        )
        assert response.status_code == 202
        response = REQUESTS_SESSION.get(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}'
        )
        assert response.json()['passtateReasonDesc'] == 'Foobar'
        logger.debug("Wait until dataset is validated")
        wait_for(
            lambda: _get_passtate(dataset_identifier)
            != DS_STATE_VALIDATING_METADATA,
            timeout=300,
            interval=5
        )
        assert _get_passtate(dataset_identifier) == DS_STATE_METADATA_CONFIRMED

        logger.debug("Preserve dataset")
        response = REQUESTS_SESSION.post(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}/preserve'
        )
        assert response.status_code == 202

        # New DPRES dataset might have been created when the dataset was
        # accepted for preservation. Check for it.
        response = REQUESTS_SESSION.get(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}'
        )
        if response.json()['pasDatasetIdentifier']:
            # switch to pas dataset
            dataset_identifier = response.json()['pasDatasetIdentifier']

        assert _get_passtate(dataset_identifier) \
            == DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION

        # Wait until dataset marked to be in digital preservation
        # (state = 120). Max wait time 5 minutes should be enough.
        wait_for(
            lambda: _get_passtate(dataset_identifier) in (
                DS_STATE_IN_DIGITAL_PRESERVATION,
                DS_STATE_REJECTED_IN_DIGITAL_PRESERVATION_SERVICE
            ),
            timeout=300,
            interval=5
        )
        assert _get_passtate(dataset_identifier) \
            == DS_STATE_IN_DIGITAL_PRESERVATION
    finally:
        print("===========================================================")
        print("Last request:")
        print(f"{response.request.method} {response.request.url}")
        print(f"Body: {response.request.body}")
        print("===========================================================")
        print("Last response:")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=4)}")
        print("===========================================================")
