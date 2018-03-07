"""Various utility methods for Flask"""
import json
import datetime

from flask import Response


def jsonify(*args, **kwargs):
    """Serialize 'obj' to a Response containing a JSON string

    datetime.datetime objects are serialized as ISO-8601 formatted
    strings

    :returns: Response containing the arguments as a JSON-encoded string

    """
    def json_serialize(obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
            raise TypeError("Type not serializable")

    if args and kwargs:
        raise TypeError(
            "jsonify() behavior undefined when passed both args and kwargs")
    elif len(args) == 1:
        data = args[0]
    else:
        data = args or kwargs

    data = json.dumps(data, default=json_serialize)

    return Response(
        data, mimetype="application/json")
