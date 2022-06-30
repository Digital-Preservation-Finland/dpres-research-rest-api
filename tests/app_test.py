"""Tests for ``research_rest_api.app`` module."""
import os
from unittest import mock

import flask
import pytest

from metax_access import ResourceNotAvailableError
from siptools_research.config import Configuration
from siptools_research.exceptions import (
    InvalidDatasetError, InvalidFileError, MissingFileError
)

from research_rest_api.app import create_app


# TODO: Use the name argument for pytest.fixture decorator to solve the
# funcarg-shadowing-fixture problem, when support for pytest version 2.x is not
# required anymore (the name argument was introduced in pytest version 3.0).
@pytest.fixture(scope="function")
def test_config(tmpdir):
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
        f"packaging_root = {temp_spool_path}",
        "mongodb_host = localhost",
        "mongodb_database = siptools-research",
        "mongodb_collection = workflow",
        "metax_url = https://metaksi",
        "metax_user = tpas",
        "metax_password = ",
        "ida_token= ",
        "dp_host = 86.50.168.218",
        "dp_user = tpas",
        "dp_ssh_key = ~/.ssh/id_rsa",
        "sip_sign_key = ~/sip_sign_pas.pem",
        "metax_ssl_verification = False",
        "pas_storage_id = urn:nbn:fi:att:file-storage-pas"
    ])

    with open(str(temp_config_path), "w+", encoding="utf-8") as config_file:
        config_file.write(config)

    return str(temp_config_path)


# TODO: Use the name argument for pytest.fixture decorator to solve the
# funcarg-shadowing-fixture problem, when support for pytest version 2.x is not
# required anymore (the name argument was introduced in pytest version 3.0).
@pytest.fixture(scope="function")
def app(test_config):
    """Create web app and Mock Metax HTTP responses.

    :returns: An instance of the REST API web app.
    """
    # Create app and change the default config file path
    app_ = create_app()
    app_.config.update(
        SIPTOOLS_RESEARCH_CONF=test_config
    )
    app_.config["TESTING"] = True

    # Create temporary directories
    conf = Configuration(test_config)
    cache_dir = os.path.join(conf.get("packaging_root"), "file_cache")
    os.mkdir(cache_dir)
    tmp_dir = os.path.join(conf.get("packaging_root"), "tmp")
    os.mkdir(tmp_dir)

    return app_


def test_index(app):
    """Test the application index page.

    :param app: Flask application
    """
    with app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 400


@mock.patch("research_rest_api.app.preserve_dataset")
def test_dataset_preserve(mock_function, app):
    """Test the preserve method.

    :param mock_function: mocked dpres_siptools function
    :param app: Flask application
    """
    with app.test_client() as client:
        response = client.post("/dataset/1/preserve")
    assert response.status_code == 202

    mock_function.assert_called_with(
        "1", app.config.get("SIPTOOLS_RESEARCH_CONF")
    )

    assert response.json == {
        "dataset_id": "1",
        "status": "packaging"
    }


@mock.patch("research_rest_api.app.generate_metadata")
def test_dataset_genmetadata(mock_function, app):
    """Test the genmetadata method.

    :param mock_function: mocked dpres_siptools function
    :param app: Flask application
    """
    with app.test_client() as client:
        response = client.post("/dataset/1/genmetadata")
    assert response.status_code == 200

    mock_function.assert_called_with(
        "1", app.config.get("SIPTOOLS_RESEARCH_CONF")
    )

    assert response.json == {
        "dataset_id": "1",
        "success": True,
        "error": "",
        "detailed_error": ""
    }


@mock.patch("research_rest_api.app.generate_metadata")
def test_dataset_genmetadata_error(mock_function, app):
    """Test that genmetadata method can handle metadata generation errors.

    :param mock_function: mocked dpres_siptools function
    :param app: Flask application
    """
    mock_function.side_effect = InvalidDatasetError("foo")

    with app.test_client() as client:
        response = client.post("/dataset/1/genmetadata")
    assert response.status_code == 400

    assert response.json == {
        "dataset_id": "1",
        "success": False,
        "error": "Dataset is invalid",
        "detailed_error": "foo"
    }


@mock.patch("research_rest_api.app.validate_metadata")
def test_validate_metadata(mock_function, app):
    """Test the validate metadata endpoint.

    :param mock_function: mocked dpres_siptools function
    :param app: Flask application
    """
    with app.test_client() as client:
        response = client.post("/dataset/1/validate/metadata")
    assert response.status_code == 200

    mock_function.assert_called_with(
        "1", app.config.get("SIPTOOLS_RESEARCH_CONF"), dummy_doi="true"
    )

    assert response.json == {
        "dataset_id": "1",
        "is_valid": True,
        "error": "",
        "detailed_error": ""
    }


@mock.patch("research_rest_api.app.validate_metadata")
def test_validate_metadata_invalid_metadata(mock_function, app):
    """Test the validate metadata endpoint when metadata is invalid.

    :param mock_function: mocked dpres_siptools function
    :param app: Flask application
    """
    mock_function.side_effect = InvalidDatasetError("foo")

    with app.test_client() as client:
        response = client.post("/dataset/2/validate/metadata")
    assert response.status_code == 200

    mock_function.assert_called_with(
        "2", app.config.get("SIPTOOLS_RESEARCH_CONF"), dummy_doi="true"
    )

    assert response.json == {
        "dataset_id": "2",
        "is_valid": False,
        "error": "Metadata did not pass validation",
        "detailed_error": "foo"
    }


@pytest.mark.parametrize(
    ("expected_response", "error"),
    [
        # Valid metadata
        (
            {
                "dataset_id": "1",
                "is_valid": True,
                "error": "",
                "detailed_error": "",
                "missing_files": [],
                "invalid_files": [],
            },
            None
        ),
        # Wrong file format in file metadata
        (
            {
                "dataset_id": "1",
                "is_valid": False,
                "error": "2 files are not well-formed",
                "detailed_error": ("2 files are not well-formed:"
                                   "\npid:urn:1\npid:urn:2"),
                "missing_files": [],
                "invalid_files": ["pid:urn:1", "pid:urn:2"],
            },
            InvalidFileError(
                "2 files are not well-formed",
                files=["pid:urn:1", "pid:urn:2"]
            )
        ),
        # Files are not available in Ida
        (
            {
                "dataset_id": "1",
                "is_valid": False,
                "error": "2 files are missing",
                "detailed_error": ("2 files are missing:"
                                   "\npid:urn:1\npid:urn:2"),
                "missing_files": ["pid:urn:1", "pid:urn:2"],
                "invalid_files": []
            },
            MissingFileError(
                "2 files are missing",
                files=["pid:urn:1", "pid:urn:2"]
            )
        ),
    ]
)
@mock.patch("research_rest_api.app.validate_files")
def test_validate_files(mock_function, app, expected_response, error):
    """Test the validate/files endpoint.

    :param mock_function: mocked dpres_siptools function
    :param app: Flask application
    :param expected_response: The response that should be shown to the user
    :param error: An error that occurs in dpres_siptools
    """
    if error:
        mock_function.side_effect = error

    with app.test_client() as client:
        response = client.post("/dataset/1/validate/files")
    assert response.status_code == 200

    mock_function.assert_called_with(
        "1", app.config.get("SIPTOOLS_RESEARCH_CONF")
    )

    assert response.json == expected_response


@pytest.mark.parametrize(
    ("code", "message", "expected_error_message", "expected_log_message"),
    [
        (404, "x", "404 Not Found: x", "404 Not Found: x"),
        (400, "x", "400 Bad Request: x", "400 Bad Request: x"),
        (500, "x", "Internal server error", "500 Internal Server Error: x"),
    ]
)
def test_http_exception_handling(
    app, caplog, code, message, expected_error_message, expected_log_message
):
    """Test that API responds with correct error messages when HTTP errors
    occur.

    :param app: Flask application
    :param caplog: log capturing instance
    :param code: status code of the HTTP error
    :param message: message given when the HTTP error is raised
    :param expected_error_message: The error message that should be shown to
                                   the user
    :param expected_log_message: The error message that should be written to
                                 the logs
    """
    @app.route("/test")
    def _raise_exception():
        """Raise exception."""
        flask.abort(code, message)

    with app.test_client() as client:
        response = client.get("/test")

    assert response.json == {
        "code": code,
        "error": expected_error_message
    }

    assert len(caplog.records) == 1
    assert caplog.records[0].message == expected_log_message


def test_metax_error_handler(app, caplog):
    """Test that API responds correctly when resource is not available in
    Metax.

    :param app: Flask application
    :param caplog: log capturing instance
    """
    error_message = "Dataset not available."

    @app.route("/test")
    def _raise_exception():
        """Raise exception."""
        raise ResourceNotAvailableError(error_message)

    with app.test_client() as client:
        response = client.get("/test")

    assert response.json == {
        "code": 404,
        "error": error_message
    }

    assert len(caplog.records) == 1
    assert caplog.records[0].message == error_message
