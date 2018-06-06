#pylint: disable=unused-variable
"""Application instance factory"""

from flask import Flask, Blueprint, request, jsonify, current_app, abort, session, json
from siptools_research import generate_metadata
from siptools_research import preserve_dataset
from siptools_research import validate_metadata
from siptools_research.utils.metax import Metax
from siptools_research.utils.metax import DatasetNotFoundError
from siptools_research.workflowtask import InvalidMetadataError
from flask_cors import CORS


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
            validity = False
            error = exc.message
            status_code = None
        except InvalidMetadataError as exc:
            validity = False
            error = exc.message
            status_code = 40
            description = "Metadata did not pass validation: %s" % error
        else:
            validity = True
            error = ''
            status_code = 70
            description = "Metadata passed validation"

        # Update preservation status in Metax. Skip the update if validation
        # failed because dataset was not found in Metax.
        if status_code:
            metax_client = Metax(app.config.get('SIPTOOLS_RESEARCH_CONF'))
            metax_client.set_preservation_state(dataset_id, status_code,
                                                description)

        response = jsonify({'dataset_id': dataset_id,
                            'is_valid': validity,
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
        generation_message = 'Technical metadata generated'
        preservation_state = 20
        error_message = ''
        success = True
        try:
            generate_metadata(dataset_id,
                              app.config.get('SIPTOOLS_RESEARCH_CONF'))
        except Exception as exc:
            success = False
            preservation_state = 30
            error_message = exc
            generation_message = exc

        metax_client = Metax(app.config.get('SIPTOOLS_RESEARCH_CONF'))
        metax_client.set_preservation_state(dataset_id, preservation_state,
                                            generation_message)
        response = jsonify({'dataset_id': dataset_id,
                            'success': success,
                            'error': error_message})
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

        response = jsonify({"code": 404, "error": str(error)})
        response.status_code = 404

        return response

    @app.errorhandler(400)
    def bad_request(error):
        """JSON response handler for the 400 - Bad request errors

        :returns: HTTP Response
        """

        response = jsonify({"code": 400, "error": str(error)})
        response.status_code = 400

        return response

    return app
