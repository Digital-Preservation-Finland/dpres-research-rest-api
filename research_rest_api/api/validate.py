"""Views for testing the framework and clients"""

from flask import Blueprint, abort
from research_rest_api.utils import jsonify

VALIDATE_API = Blueprint(
    'validate', __name__,
    url_prefix='/api/1.0/validate')


@VALIDATE_API.route('/')
def index():
    """Accessing the root URL will return a Bad Request error."""
    abort(400)


@VALIDATE_API.errorhandler(404)
def page_not_found(error):
    """JSON response handler for the 404 - Not found errors"""

    response = jsonify({"code": 404, "error": str(error)})
    response.status_code = 404

    return response


@VALIDATE_API.errorhandler(400)
def bad_request(error):
    """JSON response handler for the 400 - Bad request errors"""

    response = jsonify({"code": 400, "error": str(error)})
    response.status_code = 400

    return response


@VALIDATE_API.route('/<path:pid>/validate', methods=['POST'])
def validate(pid):
    """Handles validation of a dataset.

    :pid: PID of the dataset to be validated
    """
    return jsonify({'status':'0', 'identifier': pid  }), 200
