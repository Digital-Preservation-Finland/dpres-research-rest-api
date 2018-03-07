"""Views for testing the framework and clients"""

from flask import Blueprint, abort
from research_rest_api.utils import jsonify

SIP_API = Blueprint(
    'sip', __name__,
    url_prefix='/api/1.0/sip')


@SIP_API.route('/')
def index():
    """Accessing the root URL will return a Bad Request error."""
    abort(400)


@SIP_API.errorhandler(404)
def page_not_found(error):
    """JSON response handler for the 404 - Not found errors"""

    response = jsonify({"code": 404, "error": str(error)})
    response.status_code = 404

    return response


@SIP_API.errorhandler(400)
def bad_request(error):
    """JSON response handler for the 400 - Bad request errors"""

    response = jsonify({"code": 400, "error": str(error)})
    response.status_code = 400

    return response


@SIP_API.route('/<path:pid>/sip', methods=['POST'])
def sip(pid):
    """Simple hello world service for testing the application"""
    return jsonify({'message': 'Hello World!'})
