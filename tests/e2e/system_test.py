"""Fairdata siptools workflow system test

This is a e2e test for verifying the fairdata siptools workflow functionality.
The test simulates the Management UI (admin-web-ui) by using the REST APIs
(admin-rest-api and research-rest-api) to propose, generate metadata, validate
metadata, confirm and finally accept the dataset for digital preservation. The
test waits until the preservation_state of the dataset will be changed to "In
digital Preservation"(120). This means that the created SIP has been accepted
for digital preservation by the preservation system.

The test dataset contains one HTML file and one TIFF file

System environment setup
------------------------

Metax(metax-mockup) and IDA services are mocked.
"""
import json
import pathlib
import subprocess
import time

import pytest
import requests
import upload_rest_api.database
import urllib3
from metax_access import (DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION,
                          DS_STATE_IN_DIGITAL_PRESERVATION,
                          DS_STATE_INITIALIZED, DS_STATE_METADATA_CONFIRMED,
                          DS_STATE_PROPOSED_FOR_DIGITAL_PRESERVATION,
                          DS_STATE_REJECTED_IN_DIGITAL_PRESERVATION_SERVICE,
                          DS_STATE_TECHNICAL_METADATA_GENERATED,
                          DS_STATE_VALID_METADATA)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

METAX_API_URL = "https://metax.localhost:8443/rest/v2"
UPLOAD_API_URL = "https://packaging.localhost:8443/filestorage/api/v1"
ADMIN_API_URL = "https://manage.localhost:8443/secure/api/1.0"
REQUESTS_SESSION = requests.Session()
REQUESTS_SESSION.verify = False


def _init_upload_rest_api():
    """Add identifiers html_file_local and tiff_file_local to upload.files
    collection and create user test:test
    """
    upload_database = upload_rest_api.database.Database()
    # Adding identifiers
    files = upload_database.files
    project_path = pathlib.Path("/var/spool/upload/projects/test_project")
    identifiers = [
        {
            "_id": "valid_tiff_local",
            "file_path":  str(project_path / "valid_tiff ä.tiff")
        },
        {
            "_id": "html_file_local",
            "file_path":  str(project_path / "html_file")
        }
    ]
    files.insert(identifiers)

    # Creating test user. Project directory is created first to ensure
    # correct directory ownership.
    subprocess.run(
        ["sudo", "-u", project_path.parent.owner(), 'mkdir', project_path],
        check=True
    )
    upload_database.projects.create("test_project")
    upload_database.user("test").create(
        projects=["test_project"], password="test"
    )


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
    """
    Cleanup procedure executed before each E2E test
    """
    upload_db = upload_rest_api.database.Database()

    # Clear all applicable MongoDB collections
    # This does *not* remove indexes, matching the pre-test state more closely
    for db_name, collections in MONGO_COLLECTIONS_TO_CLEAR.items():
        mongo_db = getattr(upload_db.client, db_name)

        if collections == "*":
            collections = mongo_db.list_collection_names()

        for col_name in collections:
            coll = getattr(mongo_db, col_name)
            coll.delete_many({})

    for path in DIRS_TO_CLEAR:
        subprocess.run(
            # `-mount` ensures other filesystems (eg. sshfs) are not touched
            ["sudo", "find", path, "-mount", "-mindepth", "1", "-delete"],
            check=False
        )


@pytest.mark.parametrize("filestorage, dataset_id",
                         [("ida", 100), ("local", 101)])
def test_tpas_preservation(filestorage, dataset_id):
    """Test the whole preservation workflow using both IDA and upload-rest-api.
    """
    response = REQUESTS_SESSION.post('{}/reset'.format(METAX_API_URL))
    assert response.status_code == 200

    # Upload files through upload-rest-api
    if filestorage == "local":
        _init_upload_rest_api()

        # POST tiff file
        with open("tests/data/e2e_files/valid_tiff/download", "rb") as _file:
            response = REQUESTS_SESSION.post(
                "%s/files/test_project/valid_tiff ä.tiff" % UPLOAD_API_URL,
                auth=("test", "test"),
                data=_file
            )
        assert response.status_code == 200

        # Test that file metadata can be retrieved from files API
        response = REQUESTS_SESSION.get(
            "%s/files/test_project/valid_tiff ä.tiff" % UPLOAD_API_URL,
            auth=("test", "test")
        )
        assert response.status_code == 200
        assert response.json()['file_path'] == '/valid_tiff ä.tiff'
        assert response.json()['identifier'] == 'valid_tiff_local'
        assert response.json()['md5'] == '3cf7c3b90f5a52b2f817a1c5b3bfbc52'

        # POST html file
        with open("tests/data/e2e_files/html_file/download", "rb") as _file:
            response = REQUESTS_SESSION.post(
                "%s/files/test_project/html_file" % UPLOAD_API_URL,
                auth=("test", "test"),
                data=_file
            )
        assert response.status_code == 200

    response = REQUESTS_SESSION.get('{}/datasets/{}'.format(ADMIN_API_URL,
                                                            dataset_id))
    assert response.status_code == 200
    assert response.json()['passtate'] == DS_STATE_INITIALIZED
    _assert_preservation(response.json()['identifier'])


def _assert_preservation(dataset_identifier):
    """ Run the whole preservation workflow"""
    try:
        response = REQUESTS_SESSION.post(
            '{}/datasets/{}/propose'.format(ADMIN_API_URL, dataset_identifier),
            data={'message': 'Proposing'}
        )
        response = REQUESTS_SESSION.get(
            '{}/datasets/{}'.format(ADMIN_API_URL, dataset_identifier)
        )
        assert response.status_code == 200
        passtate = response.json()['passtate']
        assert passtate == DS_STATE_PROPOSED_FOR_DIGITAL_PRESERVATION
        assert response.json()['passtateReasonDesc'] == 'Proposing'
        response = REQUESTS_SESSION.post(
            '{}/research/dataset/{}/genmetadata'.format(ADMIN_API_URL,
                                                        dataset_identifier)
        )
        assert response.status_code == 200
        response = REQUESTS_SESSION.get(
            '{}/datasets/{}'.format(ADMIN_API_URL, dataset_identifier)
        )
        assert response.status_code == 200
        passtate = response.json()['passtate']
        assert passtate == DS_STATE_TECHNICAL_METADATA_GENERATED
        response = REQUESTS_SESSION.post(
            '{}/research/dataset/{}/validate/metadata'.format(
                ADMIN_API_URL, dataset_identifier
            )
        )
        assert response.status_code == 200
        response = REQUESTS_SESSION.get(
            '{}/datasets/{}'.format(ADMIN_API_URL, dataset_identifier)
        )
        assert response.status_code == 200
        assert response.json()['passtate'] == DS_STATE_VALID_METADATA
        response = REQUESTS_SESSION.post(
            '{}/research/dataset/{}/validate/files'.format(ADMIN_API_URL,
                                                           dataset_identifier)
        )
        assert response.status_code == 200
        response = REQUESTS_SESSION.get(
            '{}/datasets/{}'.format(ADMIN_API_URL, dataset_identifier)
        )
        assert response.status_code == 200
        assert response.json()['passtate'] == DS_STATE_VALID_METADATA
        response = REQUESTS_SESSION.post(
            '{}/datasets/{}/confirm'.format(ADMIN_API_URL, dataset_identifier),
            data={'confirmed': 'true'}
        )
        assert response.status_code == 200
        response = REQUESTS_SESSION.get(
            '{}/datasets/{}'.format(ADMIN_API_URL, dataset_identifier)
        )
        assert response.status_code == 200
        assert response.json()['passtate'] == DS_STATE_METADATA_CONFIRMED
        response = REQUESTS_SESSION.post(
            '{}/datasets/{}/preserve'.format(ADMIN_API_URL,
                                             dataset_identifier))
        assert response.status_code == 200
        response = REQUESTS_SESSION.get(
            '{}/datasets/{}'.format(ADMIN_API_URL, dataset_identifier)
        )
        assert response.status_code == 200
        passtate = response.json()['passtate']
        assert passtate == DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION
        if response.json()['isPASDataset'] is False:
            # switch to pas dataset
            dataset_identifier = response.json()['pasDatasetIdentifier']
        response = REQUESTS_SESSION.post(
            '{}/research/dataset/{}/preserve'.format(ADMIN_API_URL,
                                                     dataset_identifier)
        )
        assert response.status_code == 202

        # wait until dataset marked to be in digital preservation (state = 120)
        # max wait time 5 minutes should be enough
        counter = 0
        passtate = DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION
        while (counter < 60 and
               passtate != DS_STATE_IN_DIGITAL_PRESERVATION and
               passtate != DS_STATE_REJECTED_IN_DIGITAL_PRESERVATION_SERVICE):
            response = requests.get(
                '{}/datasets/{}'.format(ADMIN_API_URL, dataset_identifier),
                verify=False
            )
            assert response.status_code == 200
            passtate = response.json()['passtate']
            time.sleep(5)
            counter += 1
        assert passtate == DS_STATE_IN_DIGITAL_PRESERVATION
    finally:
        print("===========================================================")
        print("Last response:")
        print("Status:" + str(response.status_code))
        print("Response: " + json.dumps(response.json(), indent=4))
        print("===========================================================")
