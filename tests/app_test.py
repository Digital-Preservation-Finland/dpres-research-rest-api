"""Tests for ``research_rest_api.app`` module."""
import flask
import pytest

from metax_access import ResourceNotAvailableError


def test_index(app):
    """Test the application index page.

    :param app: Flask application
    """
    with app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 400


def test_dataset_preserve(mocker, app):
    """Test preserving dataset.

    :param mocker: pytest-mock mocker
    :param app: Flask application
    """
    mock_function = mocker.patch("siptools_research.preserve_dataset")

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


def test_dataset_generate_metadata(mocker, app):
    """Test the generating metadata.

    :param mocker: pytest-mock mocker
    :param app: Flask application
    """
    mock_function = mocker.patch("siptools_research.generate_metadata")

    with app.test_client() as client:
        response = client.post("/dataset/1/generate-metadata")
    assert response.status_code == 202

    mock_function.assert_called_with(
        "1", app.config.get("SIPTOOLS_RESEARCH_CONF")
    )

    assert response.json == {
        "dataset_id": "1",
        "status": "generating metadata"
    }


def test_dataset_validate_metadata(mocker, app):
    """Test validating dataset metadata.

    :param mocker: pytest-mock mocker
    :param app: Flask application
    """
    mock_function = mocker.patch("siptools_research.validate_metadata")

    with app.test_client() as client:
        response = client.post("/dataset/1/validate-metadata")
    assert response.status_code == 202

    mock_function.assert_called_with("1",
                                     app.config.get("SIPTOOLS_RESEARCH_CONF"))

    assert response.json \
        == {"dataset_id": "1", "status": "validating metadata"}


def test_validate_dataset(mocker, app):
    """Test validating files and metadata.

    :param mocker: pytest-mock mocker
    :param app: Flask application
    :param expected_response: The response that should be shown to the
                              user
    :param error: An error that occurs in dpres_siptools
    """
    mock_function = mocker.patch("siptools_research.validate_dataset")

    with app.test_client() as client:
        response = client.post("/dataset/1/validate")
    assert response.status_code == 202

    mock_function.assert_called_with(
        "1", app.config.get("SIPTOOLS_RESEARCH_CONF")
    )

    assert response.json == {"dataset_id": "1", "status": "validating dataset"}


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
