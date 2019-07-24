"""Tests for ``research_rest_api.app`` module"""
import re
import json

import pytest
import httpretty
import mock
import lxml

from metax_access import DS_STATE_INVALID_METADATA, DS_STATE_VALID_METADATA
from metax_access import Metax

from research_rest_api.app import create_app


def httpretty_register_file(uri, filename, match_querystring=True,
                            methods=None, status=200):
    """Helper function that reads file and registers it to httpretty."""
    if not methods:
        methods = [httpretty.GET]

    with open(filename) as open_file:
        body = open_file.read()
        for method in methods:
            httpretty.register_uri(method, uri, body, status=status,
                                   match_querystring=match_querystring)


def mock_metax():
    """Mock Metax using HTTPretty. Serve on valid metadata for dataset "1", and
    associated file "pid:urn:1" and "pid:urn:2".
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


# NOTE: This fixture is used because old httpretty version  (0.8.14) from
# centos7 RPM repositories does not work with http query strings.
@pytest.fixture
def mock_get_datacite(monkeypatch):
    """Mock Metax.get_datacite function with a function that just reads XML
    from a file.
    """
    def read_datacite_file(*args):
        datacite = lxml.etree.parse(
            'tests/data/metax_metadata/valid_datacite.xml'
        )
        return datacite
    monkeypatch.setattr(Metax, 'get_datacite', read_datacite_file)


def mock_ida():
    """Mock Metax using HTTPretty. Serve on valid metadata for dataset "1", and
    associated file "pid:urn:1" and "pid:urn:2".
    """
    httpretty_register_file(
        'https://86.50.169.61:4433/files/pid:urn:1/download',
        'tests/data/ida_files/valid_utf8'
    )
    httpretty_register_file(
        'https://86.50.169.61:4433/files/pid:urn:2/download',
        'tests/data/ida_files/valid_utf8'
    )


@pytest.fixture(scope="function")
def test_config(tmpdir):
    """Create a test configuration for siptools-research and return the
    file path.
    """
    temp_config_path = tmpdir.join(
        "etc", "siptools-research").ensure(dir=True)
    temp_config_path = temp_config_path.join("siptools-research.conf")
    temp_spool_path = tmpdir.join(
        "var", "spool", "siptools-research").ensure(dir=True)

    config = "\n".join([
        "[siptools_research]",
        "workspace_root = {}".format(temp_spool_path),
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
        "mimetypes_conf = tests/data/dpres_mimetypes.json"
    ])

    with open(str(temp_config_path), "w+") as config_file:
        config_file.write(config)

    return str(temp_config_path)


@pytest.fixture(scope="function")
def app(request, test_config):
    """Fixture that returns an instance of the REST API web app and mocks
    METAX and IDA HTTP responses
    """
    # Create app and change the default config file path
    app_ = create_app()
    app_.config.update(
        SIPTOOLS_RESEARCH_CONF=test_config
    )

    def _fin():
        httpretty.disable()

    httpretty.enable()
    request.addfinalizer(_fin)

    # Mock Metax
    mock_metax()

    # Mock Ida
    mock_ida()

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


def test_dataset_validate(app, mock_get_datacite):
    """Test the validate method.

    :returns: None
    """
    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/validate')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["error"] == ""
    assert response_body["is_valid"] is True

    # Check that preservation_state was updated
    assert httpretty.last_request().method == "PATCH"
    body = json.loads(httpretty.last_request().body)
    assert body["preservation_description"] == "Metadata passed validation"
    assert int(body["preservation_state"]) == DS_STATE_VALID_METADATA


def test_dataset_validate_invalid(app):
    """Test the validate method for invalid dataset.

    :returns: None
    """
    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/2/validate')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["is_valid"] is False

    with open("tests/data/errors/message1.txt") as message:
        assert response_body["detailed_error"] == message.read()[:-1]

    assert response_body["error"] == "'description' is a required property"
    # Check that preservation_state was updated
    assert httpretty.last_request().method == "PATCH"
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
def test_dataset_validate_invalid_file(app):
    """Test the validate method for a valid dataset containing an invalid file
    """
    with app.test_client() as client:
        response = client.post("/dataset/3/validate")
    assert response.status_code == 200

    response_body = json.loads(response.data)
    assert not response_body["is_valid"]
    with open("tests/data/errors/message2.txt") as message:
        assert response_body["detailed_error"] == message.read()[:-1]

    assert response_body["error"] == ("Validation error in metadata of "
                                      "path/to/file3: 'file_storage' is a "
                                      "required property")


# pylint: disable=invalid-name
def test_dataset_validate_unavailable(app):
    """Test validation of dataset unavailable from Metax.

    :returns: None
    """
    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/not_available_id/validate')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["dataset_id"] == "not_available_id"
    assert response_body["error"] ==\
        "Could not find metadata for dataset: not_available_id"

    # Last HTTP request should be GET, since preservation_state is not
    # updated by PATCH request
    assert httpretty.last_request().method == "GET"
