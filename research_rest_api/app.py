"""Application instance factory"""

from flask import Flask

from werkzeug.contrib.fixers import ProxyFix

import logging


def create_app():
    """Configure and return a Flask application instance.

    :debug: Will the created app run in debug mode
    :returns: Instance of flask.Flask()

    """
    logger = logging.getLogger('research-rest-api')

    app = Flask(__name__)

    # http://flask.pocoo.org/docs/0.11/deploying/wsgi-standalone/#proxy-setups
    # http://werkzeug.pocoo.org/docs/0.11/contrib/fixers/#werkzeug.contrib.fixers.ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app)

    try:
        app.config.from_pyfile('/etc/research-rest-api/research-rest-api.conf')
    except IOError:
        logger.info(
            "research-rest-api.conf doesn't exist; using default settings")
        app.config.from_object('research_rest_api.default_config')

#    app.debug = debug

    if not app.config.get("HOME_ROOT_PATH", None):
        raise RuntimeError("HOME_ROOT_PATH variable not defined!")

    from research_rest_api.api.test import API_TEST
    app.register_blueprint(API_TEST)

    from research_rest_api.api.validate import VALIDATE_API
    app.register_blueprint(VALIDATE_API)

    from research_rest_api.api.sip import SIP_API
    app.register_blueprint(SIP_API)

    return app
