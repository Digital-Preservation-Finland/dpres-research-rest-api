# pylint: disable=unused-variable
"""Application instance factory."""
import logging
import logging.handlers

from flask import Flask, jsonify, abort, current_app
from flask_cors import CORS
from requests.exceptions import HTTPError

from metax_access import ResourceNotAvailableError

from siptools_research import (generate_metadata, preserve_dataset,
                               validate_metadata, validate_files)
from siptools_research.exceptions import InvalidDatasetError
from siptools_research.exceptions import InvalidFileError
from siptools_research.exceptions import MissingFileError


logging.basicConfig(level=logging.ERROR)
LOGGER = logging.getLogger(__name__)


def create_app():
    """Configure and return a Flask application instance.

    :returns: Instance of flask.Flask()

    """
    app = Flask(__name__)
    try:
        app.config.from_pyfile('tests/data/research_rest_api.conf')
    except IOError:
        app.config.from_object('research_rest_api.default_config')

    CORS(app, resources={r"/*": {"origins": "*"}},
         supports_credentials=True)

    @app.route('/dataset/<dataset_id>/validate/metadata', methods=['POST'])
    def validate_dataset_metadata(dataset_id):
        """Validate dataset metadata.

        :returns: HTTP Response
        """
        # Validate dataset metadata

        try:
            validate_metadata(
                dataset_id,
                app.config.get('SIPTOOLS_RESEARCH_CONF'),
                dummy_doi="true"
            )
        except InvalidDatasetError as exc:
            is_valid = False
            error = "Metadata did not pass validation"
            detailed_error = str(exc)
        else:
            is_valid = True
            error = ''
            detailed_error = ''

        response = jsonify({'dataset_id': dataset_id,
                            'is_valid': is_valid,
                            'error': error,
                            'detailed_error': detailed_error})

        response.status_code = 200
        return response

    @app.route('/dataset/<dataset_id>/validate/files', methods=['POST'])
    def validate_dataset_files(dataset_id):
        """Validate dataset files.

        :returns: HTTP Response
        """
        # Validate dataset files

        try:
            validate_files(
                dataset_id,
                app.config.get('SIPTOOLS_RESEARCH_CONF')
            )
        except InvalidFileError as exc:
            is_valid = False
            error = str(exc)
            detailed_error = '{}:\n{}'.format(str(exc), '\n'.join(exc.files))
            missing_files = []
            invalid_files = exc.files
        except MissingFileError as exc:
            is_valid = False
            error = str(exc)
            detailed_error = '{}:\n{}'.format(str(exc), '\n'.join(exc.files))
            missing_files = exc.files
            invalid_files = []
        else:
            is_valid = True
            error = ''
            detailed_error = ''
            missing_files = []
            invalid_files = []

        response = jsonify({'dataset_id': dataset_id,
                            'is_valid': is_valid,
                            'missing_files': missing_files,
                            'invalid_files': invalid_files,
                            'error': error,
                            'detailed_error': detailed_error})

        response.status_code = 200
        return response

    @app.route('/dataset/<dataset_id>/preserve', methods=['POST'])
    def preserve(dataset_id):
        """Trigger packaging of dataset.

        :returns: HTTP Response
        """
        # Trigger dataset preservation using function provided by
        # siptools_research package.
        preserve_dataset(dataset_id, app.config.get('SIPTOOLS_RESEARCH_CONF'))

        response = jsonify({'dataset_id': dataset_id,
                            'status': 'packaging'})
        response.status_code = 202

        return response

    @app.route('/dataset/<dataset_id>/genmetadata', methods=['POST'])
    def genmetadata(dataset_id):
        """Generate technical metadata and store it to Metax.

        :returns: HTTP Response
        """
        try:
            generate_metadata(dataset_id,
                              app.config.get('SIPTOOLS_RESEARCH_CONF'))
        except InvalidDatasetError as exc:
            success = False
            error = "Dataset is invalid"
            detailed_error = str(exc)
            status_code = 400
        else:
            success = True
            error = ""
            detailed_error = ""
            status_code = 200

        response = jsonify({
            'dataset_id': dataset_id,
            'success': success,
            'error': error,
            'detailed_error': detailed_error
        })
        response.status_code = status_code
        return response

    @app.route('/')
    def index():
        """Return a Bad Request error."""
        abort(400)

    @app.errorhandler(404)
    def page_not_found(error):
        """Handle the 404 - Not found errors.

        :returns: HTTP Response
        """
        current_app.logger.error(error, exc_info=True)

        response = jsonify({"code": 404, "error": str(error)})
        response.status_code = 404

        return response

    @app.errorhandler(400)
    def bad_request(error):
        """JSON response handler for the 400 - Bad request errors.

        :returns: HTTP Response
        """
        current_app.logger.error(error, exc_info=True)

        response = jsonify({"code": 400, "error": str(error)})
        response.status_code = 400

        return response

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle the 500 - Internal server error.

        :returns: HTTP Response
        """
        current_app.logger.error(error, exc_info=True)

        response = jsonify({"code": 500, "error": "Internal server error"})
        response.status_code = 500

        return response

    @app.errorhandler(ResourceNotAvailableError)
    def metax_error(error):
        """Handle ResourceNotAvailableError."""
        current_app.logger.error(error, exc_info=True)

        response = jsonify({"code": 404, "error": str(error)})
        response.status_code = 404
        return response

    @app.errorhandler(HTTPError)
    def http_error(error):
        """Handle HTTPError."""
        # Log also content of response for debugging purposes
        message \
            = 'HTTP request to {} failed. Response from server was: {}'.format(
                error.response.url, error.response.text
            )
        current_app.logger.error(message)

        raise error

    return app
