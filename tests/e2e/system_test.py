"""Fairdata siptools workflow system test

This is a e2e test for verifying the fairdata siptools workflow functionality.
The test simulates the Management UI (admin-web-ui) by using the REST APIs
(admin-rest-api and research-rest-api) to propose, generate metadata, validate
metadata, confirm and finally accept the dataset for digital preservation. The
test waits until the preservation_state of the dataset will be changed to "In
digital Preservation"(120). This means that the created SIP has been accepted
for digital preservation by the preservation system.

The test dataset contains one HTML file and one TIFF file

System environment setup
------------------------

Metax(metax-mockup) and IDA services are mocked.
"""
from __future__ import print_function

import time
import json

from requests import get, post
import pytest
from upload_rest_api import database as db
from metax_access import (DS_STATE_INITIALIZED,
                          DS_STATE_PROPOSED_FOR_DIGITAL_PRESERVATION,
                          DS_STATE_TECHNICAL_METADATA_GENERATED,
                          DS_STATE_VALID_METADATA,
                          DS_STATE_METADATA_CONFIRMED,
                          DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION,
                          DS_STATE_IN_DIGITAL_PRESERVATION,
                          DS_STATE_REJECTED_IN_DIGITAL_PRESERVATION_SERVICE)


def _init_upload_rest_api():
    """Add identifiers html_file_local and tiff_file_local to upload.files
    collection and create user test:test
    """
    # Adding identifiers
    files = db.FilesCol()
    project_path = "/var/spool/upload/test_project"
    identifiers = [
        {
            "_id": "valid_tiff_local",
            "file_path": "%s/valid_tiff.tiff" % project_path
        },
        {
            "_id": "html_file_local",
            "file_path": "%s/html_file" % project_path
        }
    ]
    files.insert(identifiers)

    # Creating test user
    db.UsersDoc("test").create("test_project", password="test")


@pytest.mark.parametrize("filestorage, dataset_id",
                         [("ida", 100), ("local", 101)])
def test_tpas_preservation(filestorage, dataset_id):
    """Test the whole preservation workflow using both IDA and upload-rest-api.
    """
    response = post('http://localhost:5556/metax/rest/v1/reset')
    assert response.status_code == 200

    upload_url = "http://localhost:5556/filestorage/api/v1"

    # Upload files through upload-rest-api
    if filestorage == "local":
        _init_upload_rest_api()

        # POST tiff file
        with open("/var/www/html/files/valid_tiff/download",
                  "rb") as _file:
            response = post(
                "%s/files/valid_tiff.tiff" % upload_url,
                auth=("test", "test"), data=_file
            )
            assert response.status_code == 200

        # POST html file
        with open("/var/www/html/files/html_file/download", "rb") as _file:
            response = post(
                "%s/files/html_file" % upload_url,
                auth=("test", "test"), data=_file
            )
            assert response.status_code == 200

    response = get(
        'http://localhost:5556/admin/api/1.0/datasets/%d' % dataset_id
    )
    assert response.status_code == 200
    assert response.json()['passtate'] == DS_STATE_INITIALIZED
    _assert_preservation(response.json()['identifier'])


def _assert_preservation(dataset_identifier):
    """ Run the whole preservation workflow"""
    try:
        response = post(
            'http://localhost:5556/admin/api/1.0/'
            'datasets/%s/propose' % dataset_identifier,
            data={'message': 'Proposing'}
        )
        response = get(
            'http://localhost:5556/admin/api/1.0/datasets/%s' %
            dataset_identifier
        )
        assert response.status_code == 200
        passtate = response.json()['passtate']
        assert passtate == DS_STATE_PROPOSED_FOR_DIGITAL_PRESERVATION
        assert response.json()['passtateReasonDesc'] == 'Proposing'
        response = post(
            'http://localhost:5556/admin/api/1.0/research'
            '/dataset/%s/genmetadata' % dataset_identifier
        )
        assert response.status_code == 200
        response = get(
            'http://localhost:5556/admin/api/1.0/datasets/%s' %
            dataset_identifier
        )
        assert response.status_code == 200
        passtate = response.json()['passtate']
        assert passtate == DS_STATE_TECHNICAL_METADATA_GENERATED
        response = post(
            'http://localhost:5556/admin/api/1.0/research'
            '/dataset/%s/validate/metadata' % dataset_identifier
        )
        assert response.status_code == 200
        response = get(
            'http://localhost:5556/admin/api/1.0/datasets/%s' %
            dataset_identifier
        )
        assert response.status_code == 200
        assert response.json()['passtate'] == DS_STATE_VALID_METADATA
        response = post(
            'http://localhost:5556/admin/api/1.0/datasets'
            '/%s/confirm' % dataset_identifier,
            data={'confirmed': 'true'}
        )
        assert response.status_code == 200
        response = get(
            'http://localhost:5556/admin/api/1.0/datasets/%s' %
            dataset_identifier
        )
        assert response.status_code == 200
        assert response.json()['passtate'] == DS_STATE_METADATA_CONFIRMED
        response = post(
            'http://localhost:5556/admin/api/1.0'
            '/datasets/%s/preserve' % dataset_identifier
        )
        assert response.status_code == 200
        response = get(
            'http://localhost:5556/admin/api/1.0/datasets/%s' %
            dataset_identifier
        )
        assert response.status_code == 200
        passtate = response.json()['passtate']
        assert passtate == DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION
        if response.json()['isPASDataset'] is False:
            # switch to pas dataset
            dataset_identifier = response.json()['pasDatasetIdentifier']
        response = post(
            'http://localhost:5556/admin/api/1.0/research'
            '/dataset/%s/preserve' % dataset_identifier
        )
        assert response.status_code == 202

        # wait until dataset marked to be in digital preservation (state = 120)
        # max wait time 5 minutes should be enough
        counter = 0
        passtate = DS_STATE_ACCEPTED_TO_DIGITAL_PRESERVATION
        while (counter < 60 and
               passtate != DS_STATE_IN_DIGITAL_PRESERVATION and
               passtate != DS_STATE_REJECTED_IN_DIGITAL_PRESERVATION_SERVICE):
            response = get(
                'http://localhost:5556/admin/api/1.0/datasets/%s' %
                dataset_identifier
            )
            assert response.status_code == 200
            passtate = response.json()['passtate']
            time.sleep(5)
            counter += 1
        assert passtate == DS_STATE_IN_DIGITAL_PRESERVATION
    finally:
        print("===========================================================")
        print("Last response:")
        print("Status:" + str(response.status_code))
        print("Response: " + json.dumps(response.json(), indent=4))
        print("===========================================================")
