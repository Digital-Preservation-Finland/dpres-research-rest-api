from requests import get, post
import time

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


def test_tpas_preservation():
    response = post('http://localhost:5556/metax/rest/v1/reset')
    assert response.status_code == 200
    response = get('http://localhost:5556/admin/api/1.0/datasets/100')
    assert response.status_code == 200
    assert response.json()['passtate'] == 0
    response = post('http://localhost:5556/admin/api/1.0/datasets/100/propose',
                    data={'message': 'Proposing'})
    response = get('http://localhost:5556/admin/api/1.0/datasets/100')
    assert response.status_code == 200
    assert response.json()['passtate'] == 10
    assert response.json()['passtateReasonDesc'] == 'Proposing'
    response = post('http://localhost:5556/packaging/api/dataset/100/'
                    'genmetadata')
    assert response.status_code == 200
    response = get('http://localhost:5556/admin/api/1.0/datasets/100')
    assert response.status_code == 200
    assert response.json()['passtate'] == 20
    response = post('http://localhost:5556/packaging/api/dataset/100/validate')
    assert response.status_code == 200
    response = get('http://localhost:5556/admin/api/1.0/datasets/100')
    assert response.status_code == 200
    assert response.json()['passtate'] == 70
    response = post('http://localhost:5556/admin/api/1.0/datasets/100/confirm',
                    data={'confirmed': 'true'})
    assert response.status_code == 200
    response = get('http://localhost:5556/admin/api/1.0/datasets/'
                   '100')
    assert response.status_code == 200
    assert response.json()['passtate'] == 75
    response = post('http://localhost:5556/admin/api/1.0/datasets/'
                    '100/preserve')
    assert response.status_code == 200
    response = get('http://localhost:5556/admin/api/1.0/datasets/100')
    assert response.status_code == 200
    assert response.json()['passtate'] == 80
    response = post('http://localhost:5556/packaging/api/dataset/100/preserve')
    assert response.status_code == 202

    # wait until dataset marked to be in digital preservation (state = 120)
    # max wait time 5 minutes should be enough
    counter = 0
    passtate = 80
    while counter < 60 and passtate != 120 and passtate != 130:
        response = get('http://localhost:5556/admin/api/1.0/datasets/100')
        assert response.status_code == 200
        passtate = response.json()['passtate']
        time.sleep(5)
        counter += 1
    assert passtate == 120
