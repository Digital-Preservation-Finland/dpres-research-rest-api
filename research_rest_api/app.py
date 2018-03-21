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

    @app.route('/validate/<dataset_id>')
    def validate(dataset_id):
        """Dummy function that returns hard-coded json-message

        :returns: Dymmy json message
        """
        # TODO: Implement dataset validation triggering
        return flask.jsonify({'dataset_id': dataset_id, 'status': 'valid'})

    @app.route('/preserve/<dataset_id>')
    def preserve(dataset_id):
        """Trigger packaging of dataset.

        :returns: json message
        """

        # Trigger dataset preservation using function provided by
        # siptools_research package. Run the function in background.
        thread = threading.Thread(target=preserve_dataset,
                                  args=(dataset_id,
                                        '/etc/siptools_research.conf'))
        thread.daemon = True
        thread.start()

        # TODO: What should this response be?
        return flask.jsonify({'dataset_id': dataset_id, 'status': 'packaging'})


    @app.route('/')
    def index():
        """Accessing the root URL will return a Bad Request error."""
        flask.abort(400)


    @app.errorhandler(404)
    def page_not_found(error):
        """JSON response handler for the 404 - Not found errors"""

        response = flask.jsonify({"code": 404, "error": str(error)})
        response.status_code = 404

        return response


    @app.errorhandler(400)
    def bad_request(error):
        """JSON response handler for the 400 - Bad request errors"""

        response = flask.jsonify({"code": 400, "error": str(error)})
        response.status_code = 400

        return response

    return app
