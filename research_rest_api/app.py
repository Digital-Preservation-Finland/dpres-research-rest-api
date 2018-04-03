#pylint: disable=unused-variable
"""Application instance factory"""

import flask
from siptools_research import preserve_dataset
from siptools_research import validate_metadata
from siptools_research.utils.metax import Metax
from flask_cors import CORS


def create_app():
    """Configure and return a Flask application instance.

    :returns: Instance of flask.Flask()

    """
    app = flask.Flask(__name__)
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
        validation_result = validate_metadata(
            dataset_id, app.config.get('SIPTOOLS_RESEARCH_CONF')
        )

        if validation_result is True:
            validity = True
            error = ''
            status_code = 10
        else:
            validity = False
            error = validation_result
            status_code = 9

        metax_client = Metax(app.config.get('SIPTOOLS_RESEARCH_CONF'))
        metax_client.set_preservation_state(dataset_id, status_code,
                                            str(error))

        response = flask.jsonify({'dataset_id': dataset_id,
                                  'is_valid': validity,
                                  'error': str(error)})

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

        response = flask.jsonify({'dataset_id': dataset_id,
                                  'status': 'packaging'})
        response.status_code = 202

        return response

    @app.route('/')
    def index():
        """Accessing the root URL will return a Bad Request error."""
        flask.abort(400)

    @app.errorhandler(404)
    def page_not_found(error):
        """JSON response handler for the 404 - Not found errors

        :returns: HTTP Response
        """

        response = flask.jsonify({"code": 404, "error": str(error)})
        response.status_code = 404

        return response

    @app.errorhandler(400)
    def bad_request(error):
        """JSON response handler for the 400 - Bad request errors

        :returns: HTTP Response
        """

        response = flask.jsonify({"code": 400, "error": str(error)})
        response.status_code = 400

        return response

    return app
