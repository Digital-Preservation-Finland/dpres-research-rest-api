"""Flask web application default settings when running in debug mode."""

# default: "/home/spock"
HOME_ROOT_PATH = "/home/spock"

# default: "localhost"
MONGO_HOST = "localhost"

# default: 27017
MONGO_PORT = 27017

# default: "http://localhost"
METAX_API_HOST = "http://localhost:8888"
# METAX_API_HOST = "https://metax-test.csc.fi"

# default: "/"
METAX_BASE_PATH = "/rest/v2/"

PROPOSE_FAILS_DATASET_ID = ("urn:nbn:fi:att:cr955e904-e3dd-4d7e-99f1-"
                            "3fed446f96d2")
VALIDATION_FAILS_DATASET_ID = ("urn:nbn:fi:att:cr955e904-e3dd-4d7e-99f1-"
                               "3fed446f96d1")

# default: False
METAX_SSL_VERIFICATION = False

# default: "/secure"
SHIBBOLETH_ROOT = "/secure"

# default: False
BYPASS_AUTHENTICATION = True

# default: True
MAIL_SUPPRESS_SEND = True

# default: "localhost"
MAIL_SERVER = "localhost"

# default: "None"
MAIL_DEFAULT_SENDER = "None"

REJECT_MAIL_SUBJECT = "Dataset rejected"

REJECT_MAIL_BODY = """\
The dataset "%(dataset_name)s" was rejected at the admin service for digital preservation. The dataset is not accepted to preservation.
The following message was written as the reason:

> %(message)s


--
This message was sent by digital preservation admin service."""

REMOVE_MAIL_SUBJECT = "Dataset removed"

REMOVE_MAIL_BODY = """\
The dataset "%(dataset_name)s" was removed at the admin service for digital preservation. The dataset is deleted from preservation.
The following message was written as the reason:

> %(message)s


--
This message was sent by digital preservation admin service."""
