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
import configparser
import contextlib
import copy
import datetime
import json
import logging
import pathlib
import subprocess

import pytest
import requests
import tusclient.client
import tusclient.exceptions
from metax_access import (DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION,
                          DS_STATE_GENERATING_METADATA,
                          DS_STATE_IN_DIGITAL_PRESERVATION,
                          DS_STATE_METADATA_CONFIRMED, DS_STATE_NONE,
                          DS_STATE_REJECTED_IN_DIGITAL_PRESERVATION_SERVICE,
                          DS_STATE_TECHNICAL_METADATA_GENERATED,
                          DS_STATE_VALIDATING_METADATA, Metax)
from pymongo import MongoClient
from requests.auth import AuthBase
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from upload_rest_api.config import CONFIG
from upload_rest_api.models.project import Project
from upload_rest_api.models.user import User

from tests.utils import wait_for

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _get_upload_url():
    return json.loads(
        pathlib.Path("/usr/share/nginx/html/fddps-frontend/config.json")
        .read_text()
    )["uploadApiUrl"]


def _get_admin_url():
    return json.loads(
        pathlib.Path("/usr/share/nginx/html/fddps-frontend/config.json").read_text("utf-8")
    )["apiUrl"]


ADMIN_API_URL = f"{_get_admin_url()}/secure/api/1.0"
UPLOAD_API_URL = f"{_get_upload_url()}/v1"

DATASET = {
    "title": {
        "en": "E2e-test dataset"
    },
    "description": {
        "en": "Test description"
    },
    "fileset": {},
    "actors": [
        {
            "roles": [
                "publisher",
                "creator"
            ],
            "person": {
                "name": "Teppo Testaaja",
                "email": "test@test.com"
            },
            "organization": {
                "pref_label": {
                    "fi": "Mysteeriorganisaatio"
                }
            }
        }
    ],
    "keyword": [
        "testkeyword"
    ],
    "metadata_owner": {
        "organization": "csc.fi",
        "user": "testuser"
    },
    "data_catalog": "urn:nbn:fi:att:data-catalog-ida",
    # The dataset must have DOI at least before METS is created
    "generate_pid_on_publish": "DOI",
    "state": "published",
    # Dataset has to have access rights when publishing
    "access_rights": {
        "license": [
            {
                "url": "http://uri.suomi.fi/codelist/fairdata/license/code/CC0-1.0"
            }
        ],
        "access_type": {
            "url": "http://uri.suomi.fi/codelist/fairdata/access_type/code/open"
        },
    },
}


def _get_passtate(metax, dataset_identifier):
    dataset = metax.get_dataset(dataset_identifier)
    if dataset["preservation"]["dataset_version"]["id"]:
        return dataset["preservation"]["dataset_version"]["preservation_state"]
    else:
        return dataset["preservation"]["state"]


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


@pytest.fixture(scope="session")
def http_client():
    """
    Requests HTTP session that is configured to automatically set correct
    authentication for each FDDPS endpoint
    """
    # Yes, we're reading a configuration file using 'sudo'.
    admin_config_text = subprocess.run(
        ["sudo", "cat", "/etc/admin_rest_api.conf"],
        check=True, capture_output=True
    ).stdout.decode("utf-8")

    # The admin-rest-api configuration is actually just Python with a different
    # file extension. Read it into a dict.
    admin_config = {}
    exec(compile(admin_config_text, "config.py", "exec"), admin_config)

    # Try retrieving the JWT token from SSO endpoint. If it's mocked we can
    # just nab the cookie from the response as it doesn't actually prompt
    # the user to login.
    #
    # If not, just continue silently; if `BYPASS_AUTHENTICATION` is set to
    # `True` then admin-rest-api should skip all authentication and assume
    # the user is an admin. We should ideally remove this configuration
    # parameter, though and rely on the mocked SSO endpoint; having a
    # configuration switch to bypass authentication that also exists in
    # production code is *not* a good idea.
    response = requests.get(
        f"{admin_config['SSO_API_URL']}/login",
        params={"redirect_url": admin_config["SSO_API_URL"]},
        allow_redirects=False,
        verify=False
    )
    sso_cookies = response.cookies

    class TestAuth(AuthBase):
        def __init__(self):
            pass

        def __call__(self, request):
            """
            Check what endpoint is being called and adjust authorization
            accordingly
            """
            url = request.url

            # Use SSO cookies for admin-rest-api if they exist
            if url.startswith(ADMIN_API_URL) and sso_cookies:
                with contextlib.suppress(KeyError):
                    # Remove existing 'Cookie' header if it's already set
                    # or 'prepare_cookies' will be ignored
                    del request.headers["Cookie"]

                request.prepare_cookies(sso_cookies)

            return request

    session = requests.Session()
    session.verify = False

    session.auth = TestAuth()

    return session


@pytest.fixture(scope="function")
def metax_client():
    configuration = configparser.ConfigParser()
    # TODO: /etc/siptools_research.conf might have stricter permissions
    # in the future, so this might fail.
    configuration.read("/etc/siptools_research.conf")

    # Initialize metax client and post test dataset to Metax
    metax_client = Metax(
        url=configuration["siptools_research"]["metax_url"],
        token=configuration["siptools_research"]["metax_token"],
        verify=False,
    )
    return metax_client


@pytest.fixture(scope="function")
def tus_client():
    """
    tus client configured ready for uploads to upload-rest-api
    """
    auth_value = base64.b64encode(b"test:test").decode("utf-8")
    tus_client = tusclient.client.TusClient(
        f"{UPLOAD_API_URL}/files_tus",
        headers={
            "Authorization": f"Basic {auth_value}"
        }
    )

    return tus_client


@pytest.fixture(scope="function")
def setup_upload_rest_api():
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


def _check_uploaded_file(http_client, name, md5):
    """Check that the uploaded file was saved with the expected metadata
    and update its parent directory with use category"""
    response = http_client.get(
        f"{UPLOAD_API_URL}/files/test_project/{name}",
        auth=("test", "test")
    )
    assert response.status_code == 200

    result = response.json()
    assert result['file_path'] == f"/{name}"
    assert result['identifier'].startswith('urn:uuid:')


@pytest.mark.usefixtures("setup_upload_rest_api")
@pytest.mark.parametrize(
    "api",
    [
        "files",  # Old, deprecated POST /v1/files upload API
        "files_tus"  # New tus based upload API
    ]
)
def test_preservation_pre_ingest(metax_client, http_client, tus_client, api):
    """Test the preservation workflow using upload-rest-api TUS API."""
    def _upload_with_tus(dir_path, file_name, local_path):
        """
        Upload file to pre-ingest file storage with new tus API
        """
        try:
            tus_client.uploader(
                local_path,
                metadata={
                    "filename": file_name,
                    "project_id": "test_project",
                    "upload_path": f"{dir_path}/{file_name}",
                    "type": "file"
                },
                metadata_encoding="utf-8",
                verify_tls_cert=False
            ).upload()
        except tusclient.exceptions.TusCommunicationError as error:
            logger.error(error.response_content)
            raise

    def _upload_with_old_api(dir_path, file_name, local_path):
        """
        Upload file to pre-ingest file storage with old deprecated upload API
        """
        with open(local_path, "rb") as _file:
            response = http_client.post(
                f"{UPLOAD_API_URL}/files/test_project/{dir_path}/{file_name}",
                auth=("test", "test"),
                data=_file
            )
        response.raise_for_status()

    # Select upload function depending on the tested API
    if api == "files":
        upload_file = _upload_with_tus
    elif api == "files_tus":
        upload_file = _upload_with_old_api

    test_dir_path = (
        f"e2e-test-{api}-"
        f"{datetime.datetime.now(datetime.timezone.utc).isoformat()}"
    )
    # TODO: File validation does not tolerate '+' character. Should it?
    test_dir_path = test_dir_path.replace("+", "_")

    # Upload TIFF file
    upload_file(
        dir_path=test_dir_path,
        file_name="valid_tiff ä.tiff",
        local_path="tests/data/e2e_files/valid_tiff/download"
    )

    _check_uploaded_file(
        http_client,
        name=f"{test_dir_path}/valid_tiff ä.tiff",
        md5="3cf7c3b90f5a52b2f817a1c5b3bfbc52"
    )

    # Upload HTML file
    upload_file(
        dir_path=test_dir_path,
        file_name="html_file",
        local_path="tests/data/e2e_files/html_file/download"
    )

    _check_uploaded_file(
        http_client,
        name=f"{test_dir_path}/html_file",
        md5="31ff97b5791a2050f08f471d6205f785"
    )

    # Create dataset
    dataset = copy.deepcopy(DATASET)
    dataset["title"]["en"] = (
        f"E2E test dataset - pre-ingest file storage - "
        f"{datetime.datetime.now(datetime.timezone.utc).isoformat()}"
    )

    # Add pre-ingest files to dataset
    dataset["data_catalog"] = "urn:nbn:fi:att:data-catalog-pas"
    dataset["fileset"] = {
        "directory_actions": [
            {
                "action": "add",
                "pathname": f"/{test_dir_path}/"
            }
        ],
        "storage_service": "pas",
        "csc_project": "test_project"
    }

    # Submit dataset
    dataset = metax_client.post_dataset(dataset)
    dataset_identifier = dataset["id"]

    logger.debug("Created dataset: %s", dataset_identifier)

    _track_dataset(
        http_client=http_client,
        metax_client=metax_client,
        dataset_identifier=dataset_identifier
    )


def test_preservation_ida(http_client, metax_client):
    """Test the preservation workflow using IDA."""
    dataset = copy.deepcopy(DATASET)
    dataset["title"]["en"] = (
        f"E2E test dataset - IDA - "
        f"{datetime.datetime.now(datetime.timezone.utc).isoformat()}"
    )
    # Add IDA files to the dataset
    dataset["data_catalog"] = "urn:nbn:fi:att:data-catalog-ida"
    dataset["fileset"] = {
        # These files are added to Metax in ansible playbook
        "file_actions": [
            {
                "action": "add",
                "storage_identifier": "dfea5aa8-c9bc-4333-8eab-0b17ee6fba14"
            },
            {
                "action": "add",
                "storage_identifier": "647b22ed-3eea-4a5f-9680-17f7c5e02a41"
            }
        ],
        "storage_service": "ida",
        # This project is created in ansible playbook
        "csc_project": "system_test_project_ida"
    }

    dataset = metax_client.post_dataset(dataset)
    dataset_identifier = dataset["id"]

    logger.debug("Created dataset: %s", dataset_identifier)

    _track_dataset(
        http_client=http_client,
        metax_client=metax_client,
        dataset_identifier=dataset_identifier
    )


def _track_dataset(http_client, metax_client, dataset_identifier):
    try:
        logger.debug(
            "Ensure that the dataset does not have preservation state"
        )
        assert _get_passtate(metax_client, dataset_identifier) == DS_STATE_NONE

        logger.debug("Set agreement")
        response = http_client.post(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}/agreement',
            data={
                "identifier": "urn:uuid:abcd1234-abcd-1234-5678-abcd1234abcd"
            }
        )
        response.raise_for_status()

        logger.debug("Identify files")
        response = http_client.post(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}/generate-metadata',
        )
        response.raise_for_status()
        assert response.status_code == 202
        assert _get_passtate(metax_client, dataset_identifier) \
            == DS_STATE_GENERATING_METADATA

        logger.debug("Wait until metadata is generated")
        wait_for(
            lambda: _get_passtate(metax_client, dataset_identifier)
            != DS_STATE_GENERATING_METADATA,
            timeout=300,
            interval=5
        )
        assert _get_passtate(metax_client, dataset_identifier) \
            == DS_STATE_TECHNICAL_METADATA_GENERATED

        logger.debug("Propose dataset for preservation")
        response = http_client.post(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}/propose',
            data={'message': 'Foobar'}
        )
        response.raise_for_status()
        assert response.status_code == 202
        response = http_client.get(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}'
        )
        assert response.json()['passtateReasonDesc'] == 'Foobar'
        logger.debug("Wait until dataset is validated")
        wait_for(
            lambda: _get_passtate(metax_client, dataset_identifier)
            != DS_STATE_VALIDATING_METADATA,
            timeout=300,
            interval=5
        )
        assert _get_passtate(metax_client, dataset_identifier) \
            == DS_STATE_METADATA_CONFIRMED

        logger.debug("Preserve dataset")
        response = http_client.post(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}/preserve'
        )
        response.raise_for_status()
        assert response.status_code == 202

        # New DPRES dataset might have been created when the dataset was
        # accepted for preservation. Check for it.
        response = http_client.get(
            f'{ADMIN_API_URL}/datasets/{dataset_identifier}'
        )
        response.raise_for_status()
        if response.json()['pasDatasetIdentifier']:
            # switch to pas dataset
            dataset_identifier = response.json()['pasDatasetIdentifier']

        assert _get_passtate(metax_client, dataset_identifier) \
            == DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION

        # Wait until dataset marked to be in digital preservation
        # (state = 120). Max wait time 5 minutes should be enough.
        wait_for(
            lambda: _get_passtate(metax_client, dataset_identifier) in (
                DS_STATE_IN_DIGITAL_PRESERVATION,
                DS_STATE_REJECTED_IN_DIGITAL_PRESERVATION_SERVICE
            ),
            timeout=300,
            interval=5
        )
        assert _get_passtate(metax_client, dataset_identifier) \
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
