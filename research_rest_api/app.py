"""Application instance factory"""

from flask import Flask
from flask import jsonify
from siptools_research import preserve_dataset


def create_app():
    """Configure and return a Flask application instance.

    :returns: Instance of flask.Flask()

    """
    app = Flask(__name__)

    @app.route('/validate/<dataset_id>')
    def validate(dataset_id):
        """Dummy function that returns hard-coded json-message

        :returns: Dymmy json message
        """
        # TODO: Implement dataset validation triggering
        return jsonify({'dataset_id': dataset_id, 'status': 'valid'})

    @app.route('/preserve/<dataset_id>')
    def preserve(dataset_id):
        """Trigger packaging of dataset.

        :returns: json message
        """

        # Trigger dataset preservation using function provided by
        # siptools_research package
        preserve_dataset(dataset_id,
                         '/etc/siptools_research.conf')

        # TODO: What should this response be?
        return jsonify({'dataset_id': dataset_id, 'status': 'packaging'})

    return app
