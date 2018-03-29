"""Tests for ``research_rest_api.app`` module"""
import json
from research_rest_api.app import create_app
import httpretty

def httpretty_register_file(uri, filename):
    """Helper function that reads file and registers it to httpretty."""
    with open(filename) as open_file:
        body = open_file.read()
        httpretty.register_uri(httpretty.GET, uri, body)


def mock_metax():
    """Mock Metax using HTTPretty. Serve on valid metadata for dataset "1", and
    associated file "pid:urn:1" and "pid:urn:2".
    """
    httpretty_register_file(
        'https://metax-test.csc.fi/rest/v1/datasets/1/files',
        'tests/data/metax_metadata/valid_dataset_files.json'
    )

    httpretty_register_file('https://metax-test.csc.fi/rest/v1/datasets/1',
                            'tests/data/metax_metadata/valid_dataset.json')

    httpretty_register_file(
        'https://metax-test.csc.fi/rest/v1/files/pid:urn:1',
        'tests/data/metax_metadata/valid_file1.json'
    )

    httpretty_register_file(
        'https://metax-test.csc.fi/rest/v1/files/pid:urn:2',
        'tests/data/metax_metadata/valid_file2.json'
    )


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


@httpretty.activate
def test_dataset_preserve():
    """Test the preserve method.

    :returns: None
    """

    # Create app and change the default config file path
    app = create_app()
    app.config.update(
        SIPTOOLS_RESEARCH_CONF='tests/data/siptools_research.conf'
    )

    # Mock Metax
    mock_metax()

    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/preserve')

    assert response.status_code == 202


@httpretty.activate
def test_dataset_validate():
    """Test the validate method.

    :returns: None
    """

    # Create app and change the default config file path
    app = create_app()
    app.config.update(
        SIPTOOLS_RESEARCH_CONF='tests/data/siptools_research.conf'
    )

    # Mock Metax
    mock_metax()

    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/validate')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["is_valid"] is True


@httpretty.activate
def test_dataset_validate_unavailable():
    """Test validation of dataset unavailable from Metax.

    :returns: None
    """

    # Create app and change the default config file path
    app = create_app()
    app.config.update(
        SIPTOOLS_RESEARCH_CONF='tests/data/siptools_research.conf'
    )

    # Mock Metax
    mock_metax()

    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/not_available_id/validate')
    assert response.status_code == 200

    # Check the body of response
    response_body = json.loads(response.data)
    assert response_body["dataset_id"] == "not_available_id"
    assert response_body["error"] ==\
        "Could not find metadata for dataset: not_available_id"
