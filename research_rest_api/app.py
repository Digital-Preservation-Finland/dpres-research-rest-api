# pylint: disable=unused-variable
"""Application instance factory"""
import logging
import logging.handlers

from flask import Flask, jsonify, abort, current_app
from flask_cors import CORS
from requests.exceptions import HTTPError

from metax_access import DatasetNotFoundError, MetaxError

from siptools_research import (
    generate_metadata, preserve_dataset, validate_metadata
)
from siptools_research.metadata_generator import MetadataGenerationError
from siptools_research.workflowtask import InvalidMetadataError


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
    def validate_md(dataset_id):
        """Validates dataset metadata.

        :returns: HTTP Response
        """
        # Validate dataset metadata

        try:
            validate_metadata(
                dataset_id,
                app.config.get('SIPTOOLS_RESEARCH_CONF'),
                dummy_doi="true",
                set_preservation_state=True
            )
        except DatasetNotFoundError as exc:
            is_valid = False
            error = str(exc)
            detailed_error = error
        except InvalidMetadataError as exc:
            is_valid = False
            detailed_error = str(exc)
            error = detailed_error.split('\n')[0]
        else:
            is_valid = True
            error = ''
            detailed_error = error

        response = jsonify({'dataset_id': dataset_id,
                            'is_valid': is_valid,
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
        generate_metadata(dataset_id, app.config.get('SIPTOOLS_RESEARCH_CONF'))
        response = jsonify({
            'dataset_id': dataset_id,
            'success': True,
            'error': ''
        })
        response.status_code = 200
        return response

    @app.route('/')
    def index():
        """Accessing the root URL will return a Bad Request error."""
        abort(400)

    @app.errorhandler(404)
    def page_not_found(error):
        """JSON response handler for the 404 - Not found errors

        :returns: HTTP Response
        """
        current_app.logger.error(error, exc_info=True)

        response = jsonify({"code": 404, "error": str(error)})
        response.status_code = 404

        return response

    @app.errorhandler(400)
    def bad_request(error):
        """JSON response handler for the 400 - Bad request errors

        :returns: HTTP Response
        """
        current_app.logger.error(error, exc_info=True)

        response = jsonify({"code": 400, "error": str(error)})
        response.status_code = 400

        return response

    @app.errorhandler(500)
    def internal_server_error(error):
        """JSON response handler for the 500 - Internal server error

        :returns: HTTP Response
        """
        current_app.logger.error(error, exc_info=True)

        response = jsonify({"code": 500, "error": "Internal server error"})
        response.status_code = 500

        return response

    @app.errorhandler(MetadataGenerationError)
    def genmetadata_errorhandler(error):
        """JSON response handler for MetadataGenerationError

        :returns HTTP Response:
        """
        current_app.logger.error(error, exc_info=True)

        response = jsonify({
            'success': False,
            'error': str(error).split('\n')[0],
            'detailed_error': str(error)
        })
        response.status_code = 400

        return response

    @app.errorhandler(MetaxError)
    def metax_error(error):
        """Generic MetaxError handler"""
        current_app.logger.error(error, exc_info=True)

        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(HTTPError)
    def http_error(error):
        """HTTPError handler"""
        current_app.logger.error(error, exc_info=True)
        response = jsonify({"code": error.response.status_code,
                            "error": str(error)})
        response.status_code = error.response.status_code
        return response

    return app
