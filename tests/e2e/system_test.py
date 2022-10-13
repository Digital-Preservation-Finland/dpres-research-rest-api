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

Metax(metax-mockup) and IDA services are mocked.
"""
import base64
import json
import logging
import pathlib
import subprocess

import pytest
import requests
import tusclient.client
import tusclient.exceptions
from metax_access import (DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION,
                          DS_STATE_IN_DIGITAL_PRESERVATION,
                          DS_STATE_INITIALIZED, DS_STATE_METADATA_CONFIRMED,
                          DS_STATE_PROPOSED_FOR_DIGITAL_PRESERVATION,
                          DS_STATE_REJECTED_IN_DIGITAL_PRESERVATION_SERVICE,
                          DS_STATE_TECHNICAL_METADATA_GENERATED,
                          DS_STATE_VALID_METADATA)
from pymongo import MongoClient
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from upload_rest_api.config import CONFIG
from upload_rest_api.models import Project, User

from tests.utils import wait_for

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

METAX_API_URL = "https://metax.localhost:8443/rest/v2"
UPLOAD_API_URL = "https://packaging.localhost:8443/filestorage/api/v1"
ADMIN_API_URL = "https://manage.localhost:8443/secure/api/1.0"
REQUESTS_SESSION = requests.Session()
REQUESTS_SESSION.verify = False


def _get_passtate(dataset_identifier):
    response = requests.get(
        f'{ADMIN_API_URL}/datasets/{dataset_identifier}',
        verify=False
    )
    assert response.status_code == 200
    return response.json()['passtate']


def _init_upload_rest_api():
    """Create user test:test to upload-rest-api."""
    project_path = pathlib.Path("/var/spool/upload/projects/test_project")

    # Creating test user. Project directory is created first to ensure
    # correct directory ownership.
    subprocess.run(
        ["sudo", "-u", project_path.parent.owner(), 'mkdir', project_path],
        check=True
    )
    Project.create(identifier="test_project")
    User.create(username="test", projects=["test_project"], password="test")


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

    # Reset Metax mock
    response = REQUESTS_SESSION.post(f'{METAX_API_URL}/reset')
    assert response.status_code == 200


def _check_uploaded_file(name, md5):
    """Check that the uploaded file was saved with the expected metadata."""
    response = REQUESTS_SESSION.get(
        f"{UPLOAD_API_URL}/files/test_project/{name}",
        auth=("test", "test")
    )
    assert response.status_code == 200
    assert response.json()['file_path'] == f"/{name}"
    assert response.json()['identifier'].startswith('urn:uuid:')
    assert response.json()['md5'] == md5


def test_preservation_local():
    """Test the preservation workflow using upload-rest-api."""
    # Initialize upload-rest-api
    _init_upload_rest_api()

    # POST tiff file
    with open("tests/data/e2e_files/valid_tiff/download", "rb") as _file:
        response = REQUESTS_SESSION.post(
            f"{UPLOAD_API_URL}/files/test_project/e2e-test-local/valid_tiff ä.tiff",
            auth=("test", "test"),
            data=_file
        )
    response.raise_for_status()

    # Test that file metadata can be retrieved from files API
    _check_uploaded_file(
        name="e2e-test-local/valid_tiff ä.tiff",
        md5="3cf7c3b90f5a52b2f817a1c5b3bfbc52"
    )

    # POST html file
    with open("tests/data/e2e_files/html_file/download", "rb") as _file:
        response = REQUESTS_SESSION.post(
            f"{UPLOAD_API_URL}/files/test_project/e2e-test-local/html_file",
            auth=("test", "test"),
            data=_file
        )
    response.raise_for_status()

    # Test that file metadata can be retrieved from files API
    _check_uploaded_file(
        name="e2e-test-local/html_file",
        md5="31ff97b5791a2050f08f471d6205f785"
    )

    # Preserve dataset
    _assert_preservation(
        "urn:nbn:fi:att:111111111-1111-1111-1111-111111111111"
    )


def test_preservation_local_tus():
    """Test the preservation workflow using upload-rest-api TUS API."""
    # Initialize upload-rest-api
    _init_upload_rest_api()

    auth_value = base64.b64encode(b"test:test").decode("utf-8")
    tus_client = tusclient.client.TusClient(
        f"{UPLOAD_API_URL}/files_tus",
        headers={
            "Authorization": f"Basic {auth_value}"
        }
    )

    # Upload TIFF file
    try:
        tus_client.uploader(
            "tests/data/e2e_files/valid_tiff/download",
            metadata={
                "filename": "valid_tiff ä.tiff",
                "project_id": "test_project",
                "upload_path": "e2e-test-local-tus/valid_tiff ä.tiff",
                "type": "file"
            },
            metadata_encoding="utf-8",
            verify_tls_cert=False
        ).upload()
    except tusclient.exceptions.TusCommunicationError as error:
        logging.error(error.response_content)
        raise

    _check_uploaded_file(
        name="e2e-test-local-tus/valid_tiff ä.tiff",
        md5="3cf7c3b90f5a52b2f817a1c5b3bfbc52"
    )

    # Upload HTML file
    try:
        tus_client.uploader(
            "tests/data/e2e_files/html_file/download",
            metadata={
                "filename": "html_file",
                "project_id": "test_project",
                "upload_path": "e2e-test-local-tus/html_file",
                "type": "file"
            },
            metadata_encoding="utf-8",
            verify_tls_cert=False
        ).upload()
    except tusclient.exceptions.TusCommunicationError as error:
        logging.error(error.response_content)
        raise

    _check_uploaded_file(
        name="e2e-test-local-tus/html_file",
        md5="31ff97b5791a2050f08f471d6205f785"
    )

    # Test preservation
    _assert_preservation(
        "urn:nbn:fi:att:222222222-2222-2222-2222-222222222222"
    )


def test_preservation_ida():
    """Test the preservation workflow using IDA."""
    _assert_preservation(
        "urn:nbn:fi:att:cr955e904-e3dd-4d7e-99f1-3fed446f96d5"
    )


def _assert_preservation(dataset_identifier):
    """Run the whole preservation workflow."""
    try:
        # Ensure that the dataset is initialized
        response = REQUESTS_SESSION.get(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}'
        )
        assert _get_passtate(dataset_identifier) == DS_STATE_INITIALIZED

        # Propose dataset for preservation
        response = REQUESTS_SESSION.post(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}/propose',
            data={'message': 'Proposing'}
        )
        assert _get_passtate(dataset_identifier) \
            == DS_STATE_PROPOSED_FOR_DIGITAL_PRESERVATION
        response = REQUESTS_SESSION.get(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}'
        )
        assert response.json()['passtateReasonDesc'] == 'Proposing'

        # Generate metadata
        response = REQUESTS_SESSION.post(
            f'{ADMIN_API_URL}/research/dataset/{dataset_identifier}'
            '/genmetadata'
        )
        assert response.status_code == 200
        assert _get_passtate(dataset_identifier) \
            == DS_STATE_TECHNICAL_METADATA_GENERATED

        # Validate metadata
        response = REQUESTS_SESSION.post(
           f'{ADMIN_API_URL}/research/dataset/{dataset_identifier}/validate'
           '/metadata'
        )
        assert response.status_code == 200
        assert _get_passtate(dataset_identifier) == DS_STATE_VALID_METADATA

        # Validate files
        response = REQUESTS_SESSION.post(
            f'{ADMIN_API_URL}/research/dataset/{dataset_identifier}'
            '/validate/files'
        )
        assert response.status_code == 200
        assert _get_passtate(dataset_identifier) == DS_STATE_VALID_METADATA

        # Confirm metadata
        response = REQUESTS_SESSION.post(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}/confirm',
            data={'confirmed': 'true'}
        )
        assert response.status_code == 200
        assert _get_passtate(dataset_identifier) == DS_STATE_METADATA_CONFIRMED

        # Preserve dataset
        response = REQUESTS_SESSION.post(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}/preserve'
        )
        assert response.status_code == 200
        assert _get_passtate(dataset_identifier) \
            == DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION
        response = REQUESTS_SESSION.get(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}'
        )
        if response.json()['isPASDataset'] is False:
            # switch to pas dataset
            dataset_identifier = response.json()['pasDatasetIdentifier']
        response = REQUESTS_SESSION.post(
            f'{ADMIN_API_URL}/research/dataset/{dataset_identifier}/preserve'
        )
        assert response.status_code == 202

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
        print("Last response:")
        print("Status:" + str(response.status_code))
        print("Response: " + json.dumps(response.json(), indent=4))
        print("===========================================================")
