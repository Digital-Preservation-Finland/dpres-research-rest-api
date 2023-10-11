"""Application instance factory."""
import logging
import logging.handlers

from flask import Flask, jsonify, abort, current_app
from flask_cors import CORS

from metax_access import ResourceNotAvailableError

import siptools_research


logging.basicConfig(level=logging.ERROR)
LOGGER = logging.getLogger(__name__)


def create_app():
    """Configure and return a Flask application instance.

    :returns: Instance of flask.Flask()

    """
    app = Flask(__name__)
    app.config.from_object('research_rest_api.default_config')

    CORS(app, resources={r"/*": {"origins": "*"}},
         supports_credentials=True)

    @app.route('/dataset/<dataset_id>/validate', methods=['POST'])
    def validate_dataset(dataset_id):
        """Validate dataset metadata and files.

        :returns: HTTP Response
        """
        siptools_research.validate_dataset(
            dataset_id, app.config.get('SIPTOOLS_RESEARCH_CONF')
        )

        response = jsonify({'dataset_id': dataset_id,
                            'status': 'validating dataset'})
        response.status_code = 202

        return response

    @app.route('/dataset/<dataset_id>/preserve', methods=['POST'])
    def preserve(dataset_id):
        """Trigger preservation workflow for dataset.

        :returns: HTTP Response
        """
        # Trigger dataset preservation using function provided by
        # siptools_research package.
        siptools_research.preserve_dataset(
            dataset_id, app.config.get('SIPTOOLS_RESEARCH_CONF')
        )

        response = jsonify({'dataset_id': dataset_id,
                            'status': 'preserving'})
        response.status_code = 202

        return response

    @app.route('/dataset/<dataset_id>/generate-metadata', methods=['POST'])
    def generate_metadata(dataset_id):
        """Generate technical metadata and store it to Metax.

        :returns: HTTP Response
        """
        siptools_research.generate_metadata(
            dataset_id, app.config.get('SIPTOOLS_RESEARCH_CONF')
        )

        response = jsonify({'dataset_id': dataset_id,
                            'status': 'generating metadata'})
        response.status_code = 202

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
        response = jsonify({"code": 404, "error": str(error)})
        response.status_code = 404

        return response

    @app.errorhandler(400)
    def bad_request(error):
        """JSON response handler for the 400 - Bad request errors.

        :returns: HTTP Response
        """
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
        response = jsonify({"code": 404, "error": str(error)})
        response.status_code = 404
        return response

    return app
