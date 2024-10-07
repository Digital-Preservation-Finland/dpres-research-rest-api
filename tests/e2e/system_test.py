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
import base64
import json
import logging
import os
import pathlib
import shutil
import subprocess
import datetime
import configparser

import pytest
import requests
import tusclient.client
import tusclient.exceptions
from metax_access import (DS_STATE_IN_DIGITAL_PRESERVATION,
                          DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION,
                          DS_STATE_INITIALIZED, DS_STATE_METADATA_CONFIRMED,
                          DS_STATE_GENERATING_METADATA,
                          DS_STATE_REJECTED_IN_DIGITAL_PRESERVATION_SERVICE,
                          DS_STATE_TECHNICAL_METADATA_GENERATED,
                          DS_STATE_VALIDATING_METADATA)
from pymongo import MongoClient
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from upload_rest_api.config import CONFIG
from upload_rest_api.models.project import Project
from upload_rest_api.models.user import User

from tests.utils import wait_for

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _get_metax_url():
    # TODO: /etc/siptools_research.conf might have stricter permissions
    # in the future, so this might fail.
    data = pathlib.Path("/etc/siptools_research.conf").read_text("utf-8")

    config = configparser.ConfigParser()
    config.read_string(data)

    return config["siptools_research"]["metax_url"]


def _get_upload_url():
    return json.loads(
        pathlib.Path("/usr/share/nginx/html/fddps-frontend/config.json").read_text("utf-8")
    )["uploadApiUrl"]


def _get_admin_url():
    return json.loads(
        pathlib.Path("/usr/share/nginx/html/fddps-frontend/config.json").read_text("utf-8")
    )["apiUrl"]


METAX_API_URL = f"{_get_metax_url()}/rest/v2"
UPLOAD_API_URL = f"{_get_upload_url()}/v1"
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


@pytest.fixture(scope="session", autouse=True)
def setup_metax():
    """Setup Metax for the E2E tests.

    Since each dataset is independent from each other we only need to run
    this once per test session.
    """
    # Reset Metax.
    # 'metax-manage' is a convenience script installed by ansible-fairdata-pas.
    metax_manage_path = shutil.which(
        "metax-manage",
        path="/usr/local/bin:{}".format(os.environ.get("PATH", ""))
    )
    subprocess.run([metax_manage_path, "flush", "--noinput"], check=True)
    subprocess.run([metax_manage_path, "index_refdata"], check=True)
    subprocess.run([metax_manage_path, "reload_refdata_cache"], check=True)
    # `loadinitialdata` is really insistent that we call it in the same
    # directory with the `manage.py` file.
    subprocess.run(
        [
            "sudo", "su", "metax", "-c",
            f"cd /home/metax/metax-api/src; {metax_manage_path} "
            f"loadinitialdata"
        ],
        check=True
    )

    # Load our own custom test data
    for path in ("test_data.json", "test_datasets.json"):
        subprocess.run(
            [metax_manage_path, "loaddata", "--format", "json", "-"],
            input=(pathlib.Path("tests/data/metax") / path).read_bytes(),
            check=True
        )


def _check_uploaded_file(name, md5):
    """Check that the uploaded file was saved with the expected metadata
    and update its parent directory with use category"""
    response = REQUESTS_SESSION.get(
        f"{UPLOAD_API_URL}/files/test_project/{name}",
        auth=("test", "test")
    )
    assert response.status_code == 200

    result = response.json()
    assert result['file_path'] == f"/{name}"
    assert result['identifier'].startswith('urn:uuid:')
    assert result['md5'] == md5


def _get_parent_directory_id_for_file(file_path, project_identifier):
    """Get parent directory identifier for the given file"""
    response = REQUESTS_SESSION.get(
        f"{METAX_API_URL}/files",
        auth=("tpas", "foobar"),
        params={
            "project_identifier": project_identifier,
            "file_path": file_path,
            "limit": "1"
        }
    )
    assert response.ok

    return response.json()["results"][0]["parent_directory"]["identifier"]


def _create_dataset_with_directory(
        directory_id, name,
        data_catalog=DATA_CATALOG_PAS
):
    date = datetime.datetime.now(datetime.timezone.utc).isoformat()

    response = REQUESTS_SESSION.post(
        f"{METAX_API_URL}/datasets",
        auth=("tpas", "foobar"),
        json={
            "research_dataset": {
                "publisher": {
                    "member_of": {
                        "name": {
                            "fi": "Testiorganisaatio"
                        },
                        "@type": "Organization"
                    },
                    "name": "Teppo Testaaja",
                    "@type": "Person"
                },
                "description": {
                    "en": "This is an automated test dataset."
                },
                "creator": [
                    {
                        "member_of": {
                            "name": {
                                "fi": "Testiorganisaatio"
                            },
                            "@type": "Organization"
                        },
                        "name": "Teppo Testaaja",
                        "@type": "Person"
                    }
                ],
                "issued": "2019-01-01",
                "title": {
                    "en": f"dpres-research-rest-api E2E test -- {name} -- {date}"
                },
                "access_rights": {
                    "access_type": {
                        "identifier": "http://uri.suomi.fi/codelist/fairdata/access_type/code/open"
                    }
                },
                "directories": [
                    {
                        "identifier": directory_id,
                        "title": "Sample directory",
                        "use_category": {
                            "in_scheme": "http://uri.suomi.fi/codelist/fairdata/use_category",
                            "identifier": "http://uri.suomi.fi/codelist/fairdata/use_category/code/source",
                            "pref_label": {
                                "en": "Source material",
                                "fi": "Lähdeaineisto",
                                "und": "Lähdeaineisto"
                            }
                        }
                    }
                ]
            },
            "contract": "urn:uuid:abcd1234-abcd-1234-5678-abcd1234abcd",
            "data_catalog": data_catalog,
            "metadata_provider_org": "localhost",
            "metadata_provider_user": "root@localhost"
        }
    )
    response.raise_for_status()

    return response.json()["identifier"]


def test_preservation_local():
    """Test the preservation workflow using upload-rest-api."""
    _init_upload_rest_api()

    # POST tiff file
    with open("tests/data/e2e_files/valid_tiff/download", "rb") as _file:
        response = REQUESTS_SESSION.post(
            f"{UPLOAD_API_URL}/files/test_project/e2e-test-local/valid_tiff ä.tiff",
            auth=("test", "test"),
            data=_file
        )
    response.raise_for_status()

    directory_id = _get_parent_directory_id_for_file(
        file_path="/e2e-test-local/valid_tiff ä.tiff",
        project_identifier="test_project"
    )

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

    # Add dataset with '/e2e-test-local' directory. The immediate parent
    # directory has to be used, as dpres-siptools-research requires an use
    # category to be defined for the file's containing directory.
    dataset_id = _create_dataset_with_directory(
        directory_id=directory_id,
        name="Local test dataset"
    )

    # Preserve dataset
    _assert_preservation(dataset_id)


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
        logger.error(error.response_content)
        raise

    _check_uploaded_file(
        name="e2e-test-local-tus/valid_tiff ä.tiff",
        md5="3cf7c3b90f5a52b2f817a1c5b3bfbc52"
    )

    directory_id = _get_parent_directory_id_for_file(
        file_path="/e2e-test-local-tus/valid_tiff ä.tiff",
        project_identifier="test_project"
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
        logger.error(error.response_content)
        raise

    _check_uploaded_file(
        name="e2e-test-local-tus/html_file",
        md5="31ff97b5791a2050f08f471d6205f785"
    )

    dataset_id = _create_dataset_with_directory(
        directory_id=directory_id,
        name="Local test dataset (tus)"
    )

    # Test preservation
    _assert_preservation(dataset_id)


def test_preservation_ida():
    """Test the preservation workflow using IDA."""
    _assert_preservation("cr955e904-e3dd-4d7e-99f1-3fed446f96d5")


def _assert_preservation(dataset_identifier):
    """Run the whole preservation workflow."""
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
