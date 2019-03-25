#pylint: disable=unused-variable
"""Application instance factory"""
import logging
import logging.handlers

from flask import Flask, jsonify, abort, current_app
from metax_access import (Metax, DS_STATE_INVALID_METADATA,
                          DS_STATE_VALID_METADATA,
                          DS_STATE_TECHNICAL_METADATA_GENERATED,
                          DS_STATE_TECHNICAL_METADATA_GENERATION_FAILED,
                          DatasetNotFoundError)
from siptools_research import (
    generate_metadata, preserve_dataset, validate_metadata
)
from siptools_research.config import Configuration
from siptools_research.workflowtask import InvalidMetadataError
from flask_cors import CORS


class MetadataGenerationError(Exception):
    """Exception raised when metadata generation fails"""
    def __init__(self, dataset_id, message):
        super(MetadataGenerationError, self).__init__(message)
        self.dataset_id = dataset_id

    def __str__(self):
        return "Error generating metadata for dataset %s: %s" % (
            self.dataset_id, self.message
        )


def create_app(testing=False):
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

    # research-rest-api logging
    if not testing:
        file_handler = logging.handlers.RotatingFileHandler(
            "/var/log/siptools_research/research_rest_api.log",
            maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(
            logging.Formatter("\n[%(asctime)s - %(levelname)s]\n%(message)s")
        )
        app.logger.addHandler(file_handler)

    @app.route('/dataset/<dataset_id>/validate', methods=['POST'])
    def validate(dataset_id):
        """Validates dataset.

        :returns: HTTP Response
        """
        # Validate dataset metadata

        try:
            validate_metadata(
                dataset_id, app.config.get('SIPTOOLS_RESEARCH_CONF')
            )
        except DatasetNotFoundError as exc:
            is_valid = False
            error = exc.message
            status_code = None
        except InvalidMetadataError as exc:
            is_valid = False
            error = exc.message
            status_code = DS_STATE_INVALID_METADATA
            description = "Metadata did not pass validation: %s" % error
        else:
            is_valid = True
            error = ''
            status_code = DS_STATE_VALID_METADATA
            description = "Metadata passed validation"

        # Update preservation status in Metax. Skip the update if validation
        # failed because dataset was not found in Metax.
        if status_code:
            if len(description) > 200:
                description = description[:199]
            config_object = Configuration(
                app.config.get('SIPTOOLS_RESEARCH_CONF')
            )
            metax_client = Metax(
                config_object.get('metax_url'),
                config_object.get('metax_user'),
                config_object.get('metax_password')
            )
            metax_client.set_preservation_state(dataset_id, state=status_code,
                                                system_description=description)

        response = jsonify({'dataset_id': dataset_id,
                            'is_valid': is_valid,
                            'error': error})

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
        config_object = Configuration(app.config.get('SIPTOOLS_RESEARCH_CONF'))
        metax_client = Metax(
            config_object.get('metax_url'),
            config_object.get('metax_user'),
            config_object.get('metax_password')
        )

        try:
            generate_metadata(
                dataset_id, app.config.get('SIPTOOLS_RESEARCH_CONF')
            )
        except Exception as exc:
            preservation_state = DS_STATE_TECHNICAL_METADATA_GENERATION_FAILED
            message = str(exc)[:199] if len(str(exc)) > 200 else str(exc)

            metax_client.set_preservation_state(
                dataset_id, state=preservation_state,
                system_description=message
            )

            raise MetadataGenerationError(dataset_id, str(exc))

        metax_client.set_preservation_state(
            dataset_id, state=DS_STATE_TECHNICAL_METADATA_GENERATED,
            system_description='Technical metadata generated'
        )

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
            'dataset_id': error.dataset_id,
            'success': False,
            'error': error.message
        })
        response.status_code = 400

        return response

    return app
