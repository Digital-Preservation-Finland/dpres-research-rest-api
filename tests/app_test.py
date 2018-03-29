from research_rest_api.app import create_app

def test_index():
    """Test the application index page.

    :returns: None
    """

    # Create app and change the default config file path
    app = create_app()
    app.config.update(
        SIPTOOLS_RESEARCH_CONF='tests/data/siptools_research.conf'
    )

    # Test the response
    with app.test_client() as client:
        response = client.get('/')

    assert response.status_code == 400

def test_dataset_preserve():
    """Test the preserve method.

    :returns: None
    """

    # Create app and change the default config file path
    app = create_app()
    app.config.update(
        SIPTOOLS_RESEARCH_CONF='tests/data/siptools_research.conf'
    )

    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/preserve')

        assert response.status_code == 202


def test_dataset_validate():
    """Test the validate method.

    :returns: None
    """

    # Create app and change the default config file path
    app = create_app()
    app.config.update(
        SIPTOOLS_RESEARCH_CONF='tests/data/siptools_research.conf'
    )

    # Test the response
    with app.test_client() as client:
        response = client.post('/dataset/1/validate')

        assert response.status_code == 200
