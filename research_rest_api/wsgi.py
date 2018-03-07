"""Module that allows deployment using WSGI"""

from research_rest_api import app

application = app.create_app()
