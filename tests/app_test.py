"""Tests for ``research_rest_api.app`` module."""
import flask
import pytest

from metax_access import ResourceNotAvailableError
from siptools_research.exceptions import (
    InvalidDatasetError, InvalidFileError, MissingFileError
)


def test_index(app):
    """Test the application index page.

    :param app: Flask application
    """
    with app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 400


def test_dataset_preserve(mocker, app):
    """Test the preserve method.

    :param mocker: pytest-mock mocker
    :param app: Flask application
    """
    mock_function = mocker.patch("research_rest_api.app.preserve_dataset")

    with app.test_client() as client:
        response = client.post("/dataset/1/preserve")
    assert response.status_code == 202

    mock_function.assert_called_with(
        "1", app.config.get("SIPTOOLS_RESEARCH_CONF")
    )

    assert response.json == {
        "dataset_id": "1",
        "status": "preserving"
    }


def test_dataset_genmetadata(mocker, app):
    """Test the genmetadata method.

    :param mock_function: pytest-mock mocker
    :param app: Flask application
    """
    mock_function = mocker.patch("research_rest_api.app.generate_metadata")

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


def test_dataset_genmetadata_error(mocker, app):
    """Test generating metadata for invalid dataset.

    The API should respond with 400 "Bad request" error.

    :param mocker: pytest-mock mocker
    :param app: Flask application
    """
    mocker.patch("research_rest_api.app.generate_metadata",
                 side_effect=InvalidDatasetError('foo'))

    with app.test_client() as client:
        response = client.post("/dataset/1/genmetadata")
    assert response.status_code == 400

    assert response.json == {
        "dataset_id": "1",
        "success": False,
        "error": "Dataset is invalid",
        "detailed_error": "foo"
    }


def test_dataset_package(mocker, app):
    """Test packaging dataset.

    :param mocker: pytest-mock mocker
    :param app: Flask application
    """
    mock_function = mocker.patch("research_rest_api.app.package_dataset")

    with app.test_client() as client:
        response = client.post("/dataset/1/package")
    assert response.status_code == 202

    mock_function.assert_called_with("1",
                                     app.config.get("SIPTOOLS_RESEARCH_CONF"))

    assert response.json == {"dataset_id": "1", "status": "packaging"}


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
def test_validate_files(mocker, app, expected_response, error):
    """Test the validate/files endpoint.

    :param mocker: pytest-mock mocker
    :param app: Flask application
    :param expected_response: The response that should be shown to the
                              user
    :param error: An error that occurs in dpres_siptools
    """
    mock_function = mocker.patch("research_rest_api.app.validate_files")
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
    ("code", "expected_error_message", "expected_log_message"),
    [
        (404, "404 Not Found: foo", "404 Not Found: foo"),
        (400, "400 Bad Request: foo", "400 Bad Request: foo"),
        (500, "Internal server error", "500 Internal Server Error: foo"),
    ]
)
def test_http_exception_handling(
    app, caplog, code, expected_error_message, expected_log_message
):
    """Test HTTP error handling.

    Tests that API responds with correct error messages when HTTP errors
    occur.

    :param app: Flask application
    :param caplog: log capturing instance
    :param code: status code of the HTTP error
    :param expected_error_message: The error message that should be
                                   shown to the user
    :param expected_log_message: The error message that should be
                                 written to the logs
    """
    @app.route("/test")
    def _raise_exception():
        """Raise exception."""
        flask.abort(code, "foo")

    with app.test_client() as client:
        response = client.get("/test")

    assert response.json == {
        "code": code,
        "error": expected_error_message
    }

    if code > 499:
        assert len(caplog.records) == 1
        assert caplog.records[0].message == expected_log_message
    else:
        assert not caplog.records


def test_metax_error_handler(app, caplog):
    """Test Metax 404 error handling.

    Test that API responds correctly when resource is not available in
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

    assert len(caplog.records) == 0
