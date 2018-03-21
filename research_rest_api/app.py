#pylint: disable=unused-variable
"""Application instance factory"""

import threading
import flask
from siptools_research import preserve_dataset


def create_app():
    """Configure and return a Flask application instance.

    :returns: Instance of flask.Flask()

    """
    app = flask.Flask(__name__)


    @app.route('/dataset/<dataset_id>/validate')
    def validate(dataset_id):
        """Validates dataset.

        :returns: HTTP Response
        """
        response = flask.jsonify({'dataset_id': dataset_id,
                                  'status': 'validated',
                                  'validation_result': True})
        response.status_code = 200
        return response


    @app.route('/dataset/<dataset_id>/preserve')
    def preserve(dataset_id):
        """Trigger packaging of dataset.

        :returns: HTTP Response
        """

        # Trigger dataset preservation using function provided by
        # siptools_research package.
        preserve_dataset(dataset_id, '/etc/siptools_research.conf')

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
