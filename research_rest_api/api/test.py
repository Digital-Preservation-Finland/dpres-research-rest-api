"""Views for testing the framework and clients"""

from flask import Blueprint, jsonify
API_TEST = Blueprint('rest_api', __name__, url_prefix='/api_test/1.0')


@API_TEST.route('/hello')
def hello():
    """Simple hello world service for testing the application"""
    return jsonify({'message': 'Hello World!'})
