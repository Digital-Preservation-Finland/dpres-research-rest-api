from research_rest_api.app import create_app

def test_index():
    """Test the application index page.

    :returns: None
    """

    # Test that request without trailing slash is redirected
    with create_app().test_client() as client:
        response = client.get('/')

    assert response.status_code == 400

def test_dataset_preserve():
    """Test the preserve method.

    :returns: None
    """

    # Test that request without trailing slash is redirected
    with create_app().test_client() as client:
        response = client.get('/dataset/1/preserve')

    assert response.status_code == 202
