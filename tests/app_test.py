"""Tests for ``research_rest_api.app`` module."""
import re
import json
import os
import copy

import pytest
import httpretty
import mock
import mongomock
import pymongo

import upload_rest_api
from siptools_research.config import Configuration
from siptools_research.xml_metadata import MetadataGenerationError
from metax_access import DS_STATE_INVALID_METADATA, DS_STATE_VALID_METADATA

from research_rest_api.app import create_app

BASE_DATASET = {
    "identifier": "valid_dataset",
    "contract": {
        "id": 1,
        "identifier": "contract"
    },
    "preservation_identifier": "foo",
    "research_dataset": {
        "provenance": [
            {
                "type": {
                    "pref_label": {
                        "en": "creation"
                    }
                },
                "temporal": {
                    "end_date": "2014-12-31T08:19:58Z",
                    "start_date": "2014-01-01T08:19:58Z"
                },
                "description": {
                    "en": "Description of provenance"
                },
                "preservation_event": {
                    "identifier": "some:id",
                    "pref_label": {
                        "en": "Pre-severing"
                    }
                },
                "event_outcome": {
                    "pref_label": {
                        "en": "(:unav)"
                    }
                },
                "outcome_description": {
                    "en": "Value unavailable, possibly unknown"
                }
            }
        ],
        "files": [
            {
                "identifier": "pid:urn:1",
                "use_category": {
                    "pref_label": {
                        "en": "label1"
                    }
                }
            },
            {
                "identifier": "pid:urn:2",
                "use_category": {
                    "pref_label": {
                        "en": "label2"
                    }
                }
            }
        ]
    }
}

BASE_FILE = {
    "file_storage": {},
    "parent_directory": {
        "identifier": "pid:urn:dir:wf1"
    },
    "checksum": {
        "algorithm": "md5",
        "value": "58284d6cdd8deaffe082d063580a9df3"
    },
    "file_characteristics": {
        "file_format": "text/plain",
    }
}


@pytest.fixture(autouse=True)
def mock_upload_conf(monkeypatch):
    """Patch upload_rest_api configuration parsing."""
    monkeypatch.setattr(
        upload_rest_api.database, "parse_conf",
        lambda conf: {"MONGO_HOST": "localhost", "MONGO_PORT": 27017}
    )


def _get_file(identifier, file_storage, file_format=None, version=None):
    file_ = copy.deepcopy(BASE_FILE)
    file_['identifier'] = identifier
    file_['file_path'] = "/path/" + identifier
    file_['file_storage']['identifier'] = file_storage
    if file_format:
        file_['file_characteristics']['file_format'] = file_format
    if version:
        file_['file_characteristics']['format_version'] = version
    return file_


def _add_files_to_dataset(files, dataset):
    """Add files to dataset.

    :param: files: file identifier to be added
    :param: dataset
    :returns: ``None``
    """
    for _file in files:
        files = dataset["research_dataset"]["files"]
        files.append({
            "identifier": _file,
            "use_category": {
                "pref_label": {
                    "en": "label2"
                }
            }
        })


def httpretty_register_file(uri, filename, match_querystring=True,
                            methods=None, status=200):
    """Read file and registers it to httpretty."""
    if not methods:
        methods = [httpretty.GET]

    with open(filename) as open_file:
        body = open_file.read()
        for method in methods:
            httpretty.register_uri(method, uri, body, status=status,
                                   match_querystring=match_querystring)


def mock_metax():
    """Mock Metax using HTTPretty.

    Serve on valid metadata for dataset "1", and associated file "pid:urn:1"
    and "pid:urn:2".
    """
    httpretty_register_file(
        uri='https://metaksi/rest/v1/datasets/1/files',
        filename='tests/data/metax_metadata/valid_dataset_files.json'
    )

    httpretty_register_file(
        uri='https://metaksi/rest/v1/datasets/valid_dataset/files',
        filename='tests/data/metax_metadata/valid_dataset_files.json'
    )

    httpretty_register_file(
        uri='https://metaksi/rest/v1/datasets/3/files',
        filename='tests/data/metax_metadata/valid_dataset3_files.json'
    )

    httpretty_register_file(
        uri='https://metaksi/rest/v1/datasets/valid_dataset3/files',
        filename='tests/data/metax_metadata/valid_dataset3_files.json'
    )

    httpretty_register_file(
        'https://metaksi/rest/v1/datasets/1',
        'tests/data/metax_metadata/valid_dataset.json',
        match_querystring=True,
        methods=[httpretty.GET, httpretty.PATCH]
    )

    httpretty_register_file(
        uri='https://metaksi/rest/v1/datasets/2',
        filename='tests/data/metax_metadata/invalid_dataset2.json',
        methods=[httpretty.GET, httpretty.PATCH]
    )

    httpretty_register_file(
        uri="https://metaksi/rest/v1/datasets/3",
        filename="tests/data/metax_metadata/valid_dataset3.json",
        methods=[httpretty.GET, httpretty.PATCH]
    )

    httpretty_register_file(
        uri="https://metaksi/rest/v1/datasets/not_available_id",
        filename="tests/data/metax_metadata/not_found.json",
        methods=[httpretty.GET],
        status=404
    )

    httpretty_register_file(
        uri="https://metaksi/rest/v1/contracts/contract",
        filename="tests/data/metax_metadata/contract.json",
        methods=[httpretty.GET]
    )

    httpretty.register_uri(
        httpretty.POST,
        re.compile('https://metaksi/rpc/(.*)'),
        status=200
    )


@pytest.fixture(scope="function", name="test_config")
def fixture_test_config(tmpdir):
    """Create a test configuration for siptools-research.

    :returns: Path to configuration file
    file path.
    """
    temp_config_path = tmpdir.join("etc",
                                   "siptools-research").ensure(dir=True)
    temp_config_path = temp_config_path.join("siptools-research.conf")
    temp_spool_path = tmpdir.join("var",
                                  "spool",
                                  "siptools-research").ensure(dir=True)

    config = "\n".join([
        "[siptools_research]",
        "packaging_root = {}".format(temp_spool_path),
        "mongodb_host = localhost",
        "mongodb_database = siptools-research",
        "mongodb_collection = workflow",
        "metax_url = https://metaksi",
        "metax_user = tpas",
        "metax_password = ",
        "ida_url = https://86.50.169.61:4433",
        "ida_user = testuser_1",
        "ida_password = ",
        "dp_host = 86.50.168.218",
        "dp_user = tpas",
        "dp_ssh_key = ~/.ssh/id_rsa",
        "sip_sign_key = ~/sip_sign_pas.pem",
        "metax_ssl_verification = False",
        "mimetypes_conf = tests/data/dpres_mimetypes.json",
        "pas_storage_id = urn:nbn:fi:att:file-storage-pas"
    ])

    with open(str(temp_config_path), "w+") as config_file:
        config_file.write(config)

    return str(temp_config_path)


@pytest.fixture(scope="function", name="app")
def fixture_app(request, test_config):
    """Create web app and Mock Metax HTTP responses.

    :returns: An instance of the REST API web app.
    """
    # Create app and change the default config file path
    app_ = create_app()
    app_.config.update(
        SIPTOOLS_RESEARCH_CONF=test_config
    )
    conf = Configuration(test_config)
    cache_dir = os.path.join(conf.get("packaging_root"), "file_cache")
    os.mkdir(cache_dir)
    tmp_dir = os.path.join(conf.get("packaging_root"), "tmp")
    os.mkdir(tmp_dir)

    def _fin():
        httpretty.reset()
        httpretty.disable()

    httpretty.enable()
    request.addfinalizer(_fin)

    # Mock Metax
    mock_metax()

    # Mock Ida
    # mock_ida()

    return app_


def test_index():
    """Test the application index page.

    :returns: None
    """
    # Create app and change the default config file path
    app_ = create_app()
    app_.config.update(
        SIPTOOLS_RESEARCH_CONF='tests/data/siptools_research.conf'
    )

    # Test the response
    with app_.test_client() as client:
        response = client.get('/')

    assert response.status_code == 400


@mock.patch('research_rest_api.app.preserve_dataset')
def test_dataset_preserve(mock_function, app):
    """Test the preserve method.

    :returns: None
    """
    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/preserve')

    mock_function.assert_called_with(
        '1', app.config.get('SIPTOOLS_RESEARCH_CONF')
    )
    assert response.status_code == 202


@mock.patch('research_rest_api.app.generate_metadata')
def test_dataset_genmetadata(_, app):
    """Test the genmetadata method.

    :returns: None
    """
    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/genmetadata')

    assert response.status_code == 200


@mock.patch('research_rest_api.app.generate_metadata')
def test_dataset_genmetadata_error(generate_metadata_mock, app):
    """Test that genmetadata method can handle metadata generation errors.

    :returns: ``None``
    """
    generate_metadata_mock.side_effect = MetadataGenerationError('foo\nbar')
    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/genmetadata')

    response_json = json.loads(response.data)
    assert response_json["success"] is False
    assert response_json["error"] == 'foo'
    assert response_json["detailed_error"] == 'foo\nbar'
    assert response.status_code == 400


def test_validate_metadata(app, requests_mock):
    """Test the validate metadata endpoint.

    :returns: None
    """
    with open('tests/data/metax_metadata/valid_dataset.json') as file_:
        mocked_response = json.load(file_)
    requests_mock.get("https://metaksi/rest/v1/datasets/1",
                      json=mocked_response)

    with open("tests/data/metax_metadata/contract.json") as file_:
        mocked_response = json.load(file_)
    requests_mock.get("https://metaksi/rest/v1/contracts/contract",
                      json=mocked_response)

    with open('tests/data/metax_metadata/valid_dataset_files.json') as file_:
        mocked_response = json.load(file_)
    requests_mock.get("https://metaksi/rest/v1/datasets/valid_dataset/files",
                      json=mocked_response)
    requests_mock.get("https://metaksi/rest/v1/datasets/1/files",
                      json=mocked_response)

    requests_mock.get("https://metaksi/rest/v1/directories/pid:urn:dir:wf1",
                      json={"directory_path": "foo"})

    requests_mock.patch("https://metaksi/rest/v1/datasets/1", json={})

    with open("tests/data/metax_metadata/valid_datacite.xml") as file_:
        mocked_response = file_.read()
    requests_mock.get(
        ("https://metaksi/rest/v1/datasets/1?dataset_format=datacite&"
         "dummy_doi=true"),
        text=mocked_response,
        complete_qs=True
    )

    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/validate/metadata')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["error"] == ""
    assert response_body["is_valid"] is True

    # Check that preservation_state was updated
    assert requests_mock.last_request.method == "PATCH"
    assert requests_mock.last_request.url == (
        "https://metaksi/rest/v1/datasets/1"
    )
    body = json.loads(requests_mock.last_request.body)
    assert body["preservation_description"] == "Metadata passed validation"
    assert int(body["preservation_state"]) == DS_STATE_VALID_METADATA


def test_validate_metadata_invalid_dataset(app):
    """Test the validate metadata endpoint with invalid dataset metadata.

    :returns: None
    """
    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/2/validate/metadata')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["is_valid"] is False

    assert response_body["error"] == "'description' is a required property"
    # Check that preservation_state was updated
    assert httpretty.last_request().method == "PATCH"
    assert httpretty.last_request().path == "/rest/v1/datasets/2"
    body = json.loads(httpretty.last_request().body)
    assert body["preservation_description"] == (
        "Metadata did not pass validation: 'description' is a required "
        "property\n"
        "\n"
        "Failed validating 'required' in schema['properties']"
        "['research_dataset']['properties']['provenance']['items']:\n"
        "    {'properties"
    )
    assert int(body["preservation_state"]) == DS_STATE_INVALID_METADATA


# pylint: disable=invalid-name
def test_validate_metadata_invalid_file(app):
    """Test the validate metadata end point with invalid file metadata.

    returns: ``None``
    """
    with app.test_client() as client:
        response = client.post("/dataset/3/validate/metadata")
    assert response.status_code == 200

    response_body = json.loads(response.data)
    assert not response_body["is_valid"]

    assert response_body["error"] == ("Validation error in metadata of "
                                      "path/to/file3: 'file_storage' is a "
                                      "required property")


# pylint: disable=invalid-name
def test_validate_metadata_dataset_unavailable(app):
    """Test validation of dataset unavailable from Metax.

    :returns: None
    """
    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/not_available_id/validate/metadata')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["dataset_id"] == "not_available_id"
    assert response_body["error"] == "Dataset not found"

    # Last HTTP request should be GET, since preservation_state is not
    # updated by PATCH request
    assert httpretty.last_request().method == "GET"


@pytest.mark.parametrize(
    "filestorage",
    ["ida", "pas"]
)
def test_validate_files(app, requests_mock, monkeypatch, filestorage):
    """Test the validate/files endpoint.

    :returns: None
    """
    _init_mongo(app, monkeypatch)

    dataset = copy.deepcopy(BASE_DATASET)
    requests_mock.get("https://metaksi/rest/v1/datasets/1",
                      json=dataset)
    _add_files_to_dataset(["pid:urn:1", "pid:urn:2"],
                          dataset)
    files = [_get_file("pid:urn:1", filestorage),
             _get_file("pid:urn:2", filestorage)]
    requests_mock.get("https://metaksi/rest/v1/datasets/1/files", json=files)
    requests_mock.get("https://86.50.169.61:4433/files/pid:urn:1/download",
                      text='This file is valid UTF-8')
    requests_mock.get("https://86.50.169.61:4433/files/pid:urn:2/download",
                      text='This file is valid UTF-8')

    requests_mock.patch("https://metaksi/rest/v1/datasets/1", json={})

    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/validate/files')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["error"] == ""
    assert response_body["is_valid"] is True

    # Check that preservation_state was updated
    assert requests_mock.last_request.method == "PATCH"
    assert requests_mock.last_request.url == (
        "https://metaksi/rest/v1/datasets/1"
    )
    body = json.loads(requests_mock.last_request.body)
    assert body["preservation_description"] == "Files passed validation"
    assert int(body["preservation_state"]) == DS_STATE_VALID_METADATA


@pytest.mark.parametrize(
    "filestorage",
    ["ida", "pas"]
)
def test_validate_files_fails(app, requests_mock, monkeypatch, filestorage):
    """Test the validate/files endpoint. File validation fails.

    :returns: None
    """
    _init_mongo(app, monkeypatch)

    dataset = copy.deepcopy(BASE_DATASET)
    requests_mock.get("https://metaksi/rest/v1/datasets/1",
                      json=dataset)
    _add_files_to_dataset(["pid:urn:1", "pid:urn:2"],
                          dataset)
    file1 = _get_file("pid:urn:1", filestorage,
                      file_format="image/tiff", version="6.0")
    file2 = _get_file("pid:urn:2", filestorage,
                      file_format="image/tiff", version="6.0")
    files = [file1, file2]
    requests_mock.get("https://metaksi/rest/v1/datasets/1/files", json=files)
    requests_mock.get("https://86.50.169.61:4433/files/pid:urn:1/download",
                      text='This file is valid UTF-8')
    requests_mock.get("https://86.50.169.61:4433/files/pid:urn:2/download",
                      text='This file is valid UTF-8')

    requests_mock.patch("https://metaksi/rest/v1/datasets/1", json={})

    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/validate/files')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["error"].startswith(
        "Following files are not well-formed:"
    )
    assert response_body["is_valid"] is False

    # Check that preservation_state was updated
    assert requests_mock.last_request.method == "PATCH"
    assert requests_mock.last_request.url == (
        "https://metaksi/rest/v1/datasets/1"
    )
    body = json.loads(requests_mock.last_request.body)
    assert body["preservation_description"].startswith(
        "Following files are not well-formed:"
    )
    assert int(body["preservation_state"]) == DS_STATE_INVALID_METADATA


def _init_mongo(app, monkeypatch):
    conf = Configuration(app.config.get('SIPTOOLS_RESEARCH_CONF'))
    mongoclient = mongomock.MongoClient()
    # pylint: disable=unused-argument

    def mock_mongoclient(*_args, **_kwargs):
        """Return already initialized mongomock.MongoClient."""
        return mongoclient
    monkeypatch.setattr(pymongo, 'MongoClient', mock_mongoclient)

    mongoclient = pymongo.MongoClient(host='localhost')
    files_col = mongoclient.upload.files

    files = [
        "pid:urn:1",
        "pid:urn:2",
    ]
    for _file in files:
        filepath = os.path.abspath(conf.get('packaging_root') +
                                   "/tmp/%s" % _file)
        fil = open(filepath, 'w+')
        fil.write('This file is valid UTF-8')
        fil.close()
        files_col.insert_one({
            "_id": _file,
            "file_path": filepath
        })
