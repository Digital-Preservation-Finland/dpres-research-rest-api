"""Fairdata siptools workflow system test

This is a e2e test for verifying the fairdata siptools workflow functionality.
The test simulates the Management UI (admin-web-ui) by using the REST APIs
(admin-rest-api and research-rest-api) to propose, generate metadata, validate,
confirm and finally accept the dataset for digital preservation. The test waits
until the preservation_state of the dataset will be changed to "In digital
Preservation"(120). This means that the created SIP has been accepted for
digital preservation by the preservation system.

The test dataset contains one HTML file and one TIFF file

System environment setup
------------------------

Metax(metax-mockup) and IDA services are mocked.
"""
import time

from requests import get, post
import pytest
from json import dumps
from upload_rest_api import database as db


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


@pytest.mark.parametrize("filestorage", ["ida", "local"])
def test_tpas_preservation(filestorage):
    """Test the whole preservation workflow using both IDA and upload-rest-api.
    """
    response = post('http://localhost:5556/metax/rest/v1/reset')
    assert response.status_code == 200

    dataset_id = 100 if filestorage == "ida" else 101
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
    assert response.json()['passtate'] == 0
    _assert_preservation(dataset_id)


def _assert_preservation(dataset_id):
    """ Run the whole preservation workflow"""
    try:
        response = post(
            'http://localhost:5556/admin/api/1.0/'
            'datasets/%d/propose' % dataset_id,
            data={'message': 'Proposing'}
        )
        response = get(
            'http://localhost:5556/admin/api/1.0/datasets/%d' % dataset_id
        )
        assert response.status_code == 200
        assert response.json()['passtate'] == 10
        assert response.json()['passtateReasonDesc'] == 'Proposing'
        response = post(
            'http://localhost:5556/admin/api/1.0/research'
            '/dataset/%d/genmetadata' % dataset_id
        )
        assert response.status_code == 200
        response = get(
            'http://localhost:5556/admin/api/1.0/datasets/%d' % dataset_id
        )
        assert response.status_code == 200
        assert response.json()['passtate'] == 20
        response = post(
            'http://localhost:5556/admin/api/1.0/research'
            '/dataset/%d/validate' % dataset_id
        )
        assert response.status_code == 200
        response = get(
            'http://localhost:5556/admin/api/1.0/datasets/%d' % dataset_id
        )
        assert response.status_code == 200
        assert response.json()['passtate'] == 70
        response = post(
            'http://localhost:5556/admin/api/1.0/datasets'
            '/%d/confirm' % dataset_id,
            data={'confirmed': 'true'}
        )
        assert response.status_code == 200
        response = get(
            'http://localhost:5556/admin/api/1.0/datasets/%d' % dataset_id
        )
        assert response.status_code == 200
        assert response.json()['passtate'] == 75
        response = post(
            'http://localhost:5556/admin/api/1.0'
            '/datasets/%d/preserve' % dataset_id
        )
        assert response.status_code == 200
        response = get(
            'http://localhost:5556/admin/api/1.0/datasets/%d' % dataset_id
        )
        assert response.status_code == 200
        assert response.json()['passtate'] == 80
        response = post(
            'http://localhost:5556/admin/api/1.0/research'
            '/dataset/%d/preserve' % dataset_id
        )
        assert response.status_code == 202

        # wait until dataset marked to be in digital preservation (state = 120)
        # max wait time 10 minutes should be enough
        counter = 0
        passtate = 80
        while counter < 120 and passtate != 120 and passtate != 130:
            response = get(
                'http://localhost:5556/admin/api/1.0/datasets/%d' % dataset_id
            )
            assert response.status_code == 200
            passtate = response.json()['passtate']
            time.sleep(5)
            counter += 1
        assert passtate == 120
    finally:
        print "==========================================================="
        print "Last response:"
        print "Status:" + str(response.status_code)
        print "Response: " + dumps(response.json())
        print "==========================================================="
