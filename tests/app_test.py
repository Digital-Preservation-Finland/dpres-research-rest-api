"""Tests for ``research_rest_api.app`` module"""
import json
import pytest
from research_rest_api.app import create_app
import httpretty
from metax_access import DS_STATE_INVALID_METADATA, DS_STATE_VALID_METADATA
import mock


def httpretty_register_file(uri, filename, methods=None, status=200):
    """Helper function that reads file and registers it to httpretty."""
    if not methods:
        methods = [httpretty.GET]

    with open(filename) as open_file:
        body = open_file.read()
        for method in methods:
            httpretty.register_uri(method, uri, body, status=status)


def mock_metax():
    """Mock Metax using HTTPretty. Serve on valid metadata for dataset "1", and
    associated file "pid:urn:1" and "pid:urn:2".
    """
    httpretty_register_file(
        uri='https://metax-test.csc.fi/rest/v1/datasets/1/files',
        filename='tests/data/metax_metadata/valid_dataset_files.json'
    )

    httpretty_register_file(
        uri=('https://metax-test.csc.fi/rest/v1/datasets/'
             '1?dataset_format=datacite'),
        filename='tests/data/metax_metadata/valid_datacite.xml',
        methods=[httpretty.GET]
    )

    httpretty_register_file(
        uri='https://metax-test.csc.fi/rest/v1/datasets/1',
        filename='tests/data/metax_metadata/valid_dataset.json',
        methods=[httpretty.GET, httpretty.PATCH]
    )

    httpretty_register_file(
        uri='https://metax-test.csc.fi/rest/v1/files/pid:urn:1',
        filename='tests/data/metax_metadata/valid_file1.json',
        methods=[httpretty.GET, httpretty.PATCH]
    )

    httpretty_register_file(
        uri='https://metax-test.csc.fi/rest/v1/files/pid:urn:2',
        filename='tests/data/metax_metadata/valid_file2.json',
        methods=[httpretty.GET, httpretty.PATCH]
    )

    httpretty_register_file(
        uri='https://metax-test.csc.fi/rest/v1/datasets/2',
        filename='tests/data/metax_metadata/invalid_dataset2.json',
        methods=[httpretty.GET, httpretty.PATCH]
    )

    httpretty_register_file(
        uri="https://metax-test.csc.fi/rest/v1/datasets/3",
        filename="tests/data/metax_metadata/valid_dataset3.json",
        methods=[httpretty.GET, httpretty.PATCH]
    )

    httpretty_register_file(
        uri="https://metax-test.csc.fi/rest/v1/files/pid:urn:3",
        filename="tests/data/metax_metadata/invalid_file3.json",
        methods=[httpretty.GET, httpretty.PATCH]
    )

    httpretty_register_file(
        uri="https://metax-test.csc.fi/rest/v1/datasets/not_available_id",
        filename="tests/data/metax_metadata/not_found.json",
        methods=[httpretty.GET],
        status=404
    )

    httpretty_register_file(
        uri="https://metax-test.csc.fi/rest/v1/contracts/contract",
        filename="tests/data/metax_metadata/contract.json",
        methods=[httpretty.GET]
    )


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
    """
    Create a test configuration for siptools-research and return the file path
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
        "metax_url = https://metax-test.csc.fi",
        "metax_user = tpas",
        "metax_password = ",
        "ida_url = https://86.50.169.61:4433",
        "ida_user = testuser_1",
        "ida_password = ",
        "dp_host = 86.50.168.218",
        "dp_user = tpas",
        "dp_ssh_key = ~/.ssh/id_rsa",
        "sip_sign_key = ~/sip_sign_pas.pem"
    ])

    with open(str(temp_config_path), "w+") as f:
        f.write(config)

    return str(temp_config_path)


@pytest.fixture(scope="function")
def app(request, test_config):
    """
    Fixture that returns an instance of the REST API web app and mocks
    METAX and IDA HTTP responses
    """
    # Create app and change the default config file path
    app = create_app()
    app.config.update(
        SIPTOOLS_RESEARCH_CONF=test_config
    )

    def fin():
        httpretty.disable()

    httpretty.enable()
    request.addfinalizer(fin)

    # Mock Metax
    mock_metax()

    # Mock Ida
    mock_ida()

    return app


def test_index():
    """Test the application index page.

    :returns: None
    """

    # Create app and change the default config file path
    app = create_app()
    app.config.update(
        SIPTOOLS_RESEARCH_CONF='tests/data/siptools_research.conf'
    )

    # Test the response
    with app.test_client() as client:
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


def test_dataset_genmetadata(app):
    """Test the genmetadata method.

    :returns: None
    """
    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/genmetadata')

    assert response.status_code == 200


def test_dataset_validate(app):
    """Test the validate method.

    :returns: None
    """
    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/validate')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["is_valid"] is True
    assert response_body["error"] == ""

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
    assert response_body["error"] == (
        """'description' is a required property

Failed validating 'required' in schema['properties']['research_dataset']['properties']['provenance']['items']:
    {'properties': {'description': {'required': ['en'], 'type': 'object'},
                    'preservation_event': {'properties': {'identifier': {'type': 'string'},
                                                          'pref_label': {'required': ['en'],
                                                                         'type': 'object'}},
                                           'required': ['identifier',
                                                        'pref_label'],
                                           'type': 'object'},
                    'temporal': {'required': ['start_date'],
                                 'type': 'object'}},
     'required': ['preservation_event', 'temporal', 'description'],
     'type': 'object'}

On instance['research_dataset']['provenance'][0]:
    {u'preservation_event': {u'identifier': u'some:id',
                             u'pref_label': {u'en': u'Perseveration'}},
     u'temporal': {u'end_date': u'2014-12-31T08:19:58Z',
                   u'start_date': u'2014-01-01T08:19:58Z'},
     u'type': {u'pref_label': {u'en': u'creation'}}}""")

    # Check that preservation_state was updated
    assert httpretty.last_request().method == "PATCH"
    body = json.loads(httpretty.last_request().body)
    assert body["preservation_description"] == (
        """Metadata did not pass validation: 'description' is a required property

Failed validating 'required' in schema['properties']['research_dataset']['properties']['provenance']['items']:
    {'properties': {'description': {'required': ['en'], 'type': 'object'},
                    'preservation_event': {'properties': {'identifier': {'type': 'string'},
                                                          'pref_label': {'required': ['en'],
                                                                         'type': 'object'}},
                                           'required': ['identifier',
                                                        'pref_label'],
                                           'type': 'object'},
                    'temporal': {'required': ['start_date'],
                                 'type': 'object'}},
     'required': ['preservation_event', 'temporal', 'description'],
     'type': 'object'}

On instance['research_dataset']['provenance'][0]:
    {u'preservation_event': {u'identifier': u'some:id',
                             u'pref_label': {u'en': u'Perseveration'}},
     u'temporal': {u'end_date': u'2014-12-31T08:19:58Z',
                   u'start_date': u'2014-01-01T08:19:58Z'},
     u'type': {u'pref_label': {u'en': u'creation'}}}"""
     )
    assert int(body["preservation_state"]) == DS_STATE_INVALID_METADATA


def test_dataset_validate_invalid_file(app):
    """
    Test the validate method for a valid dataset containing an invalid
    file
    """
    with app.test_client() as client:
        response = client.post("/dataset/3/validate")
    assert response.status_code == 200

    response_body = json.loads(response.data)
    assert not response_body["is_valid"]
    assert response_body["error"] == (
        """Validation error in metadata of path/to/file3: 'file_format' is a required property

Failed validating 'required' in schema['properties']['file_characteristics']:
    {'properties': {'file_encoding': {'enum': ['ISO-8859-15',
                                               'UTF-8',
                                               'UTF-16',
                                               'UTF-32'],
                                      'type': 'string'}},
     'required': ['file_format'],
     'type': 'object'}

On instance['file_characteristics']:
    {u'file_created': u'2014-01-17T08:19:31Z'}"""
    )


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
