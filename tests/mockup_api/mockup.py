# pylint: disable=unused-variable
"""Application instance factory"""
import time

import flask
from flask import current_app, abort
from requests import patch
from requests.exceptions import ConnectionError

from flask_cors import CORS
from metax_access import (DS_STATE_VALID_METADATA,
                          DS_STATE_METADATA_VALIDATION_FAILED,
                          DS_STATE_TECHNICAL_METADATA_GENERATED,
                          DS_STATE_TECHNICAL_METADATA_GENERATION_FAILED,
                          DS_STATE_IN_DIGITAL_PRESERVATION)

app = flask.Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}},
     supports_credentials=True)

app.config.from_object('tests.mockup_api.default_config')


@app.route('/packaging/api/dataset/<dataset_id>/validate/metadata',
           methods=['POST'])
def validate_md(dataset_id):
    """Validates dataset.

    :returns: HTTP Response
    """
    time.sleep(2)
    data = {}
    # Set defaults
    is_valid = True
    preservation_state = DS_STATE_VALID_METADATA
    preservation_description = 'Metadata passed validation'
    error = ''
    if dataset_id == app.config.get('VALIDATION_FAILS_DATASET_ID'):
        error = 'Something went wrong'
        preservation_state = DS_STATE_METADATA_VALIDATION_FAILED
        preservation_description = 'Metadata did not pass validation: ' + error
        is_valid = False
    data['preservation_state'] = preservation_state
    data['preservation_description'] = preservation_description
    set_preservation_state(dataset_id, data)

    response = flask.jsonify({'dataset_id': dataset_id,
                              'is_valid': is_valid,
                              'error': error})

    response.status_code = 200
    return response


@app.route('/packaging/api/dataset/<dataset_id>/validate/files',
           methods=['POST'])
def validate_dataset_files(dataset_id):
    """Validates dataset.

    :returns: HTTP Response
    """
    time.sleep(2)
    data = {}
    # Set defaults
    is_valid = True
    preservation_state = DS_STATE_VALID_METADATA
    preservation_description = 'Files passed validation'
    error = ''
    if dataset_id == app.config.get('VALIDATION_FAILS_DATASET_ID'):
        error = 'Following files are not well-formed:\npath1\npath2\npath3'
        preservation_state = DS_STATE_METADATA_VALIDATION_FAILED
        preservation_description = error
        is_valid = False
    data['preservation_state'] = preservation_state
    data['preservation_description'] = preservation_description
    set_preservation_state(dataset_id, data)

    response = flask.jsonify({'dataset_id': dataset_id,
                              'is_valid': is_valid,
                              'error': error})

    response.status_code = 200
    return response


@app.route('/packaging/api/dataset/<dataset_id>/preserve', methods=['POST'])
def preserve(dataset_id):
    """Trigger packaging of dataset.

    :returns: HTTP Response
    """
    time.sleep(2)
    data = {}
    data['preservation_state'] = DS_STATE_IN_DIGITAL_PRESERVATION
    data['preservation_description'] = 'In packaging service'
    set_preservation_state(dataset_id, data)

    response = flask.jsonify({'dataset_id': dataset_id,
                              'status': 'packaging'})
    response.status_code = 202

    return response


@app.route('/packaging/api/dataset/<dataset_id>/genmetadata', methods=['POST'])
def genmetadata(dataset_id):
    """Trigger packaging of dataset.

    :returns: HTTP Response
    """
    time.sleep(2)
    data = {}
    success = True
    error = ''
    preservation_state = DS_STATE_TECHNICAL_METADATA_GENERATED
    preservation_description = 'Metadata generated'
    if dataset_id == app.config.get('PROPOSE_FAILS_DATASET_ID'):
        error = 'Metadata generation failed'
        preservation_state = DS_STATE_TECHNICAL_METADATA_GENERATION_FAILED
        preservation_description = 'Propose failed: ' + error
        success = False
    data['preservation_state'] = preservation_state
    data['preservation_description'] = preservation_description
    set_preservation_state(dataset_id, data)

    response = flask.jsonify({'dataset_id': dataset_id,
                              'success': success,
                              'error': error})
    response.status_code = 200
    return response


def set_preservation_state(dataset_id, data):
    try:
        r = patch("".join([current_app.config['METAX_API_HOST'],
                           current_app.config['METAX_BASE_PATH'],
                           "datasets/", dataset_id]),
                  json=data,
                  verify=False)
        if r.status_code == 404:
            abort(404)
        elif r.status_code >= 300:
            abort(500)
    except ConnectionError:
        abort(503)


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
