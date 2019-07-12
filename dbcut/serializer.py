# -*- coding: utf-8 -*-
import datetime
import decimal
import json
import uuid

from io import open
from sqlalchemy.orm import Query

from .compat import to_unicode


class JSONEncoder(json.JSONEncoder):
    """JSON Encoder class that handles conversion for a number of types not
    supported by the default json library, especially the sqlalchemy objects.

    :returns: object that can be converted to json
    """

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            representation = obj.isoformat()
            if representation.endswith("+00:00"):
                representation = representation[:-6] + "Z"
            return to_unicode(representation)
        if isinstance(obj, (datetime.date, datetime.time)):
            return to_unicode(obj.isoformat())
        elif isinstance(obj, (decimal.Decimal)):
            return float(obj)
        elif isinstance(obj, uuid.UUID):
            return to_unicode(obj)
        elif isinstance(obj, Query):
            return list(obj)
        elif isinstance(obj, bytes):
            return obj.decode()
        elif hasattr(obj, "tolist"):
            return obj.tolist()
        elif hasattr(obj, "to_dict"):
            return obj.to_dict()
        elif hasattr(obj, "__getitem__"):
            try:
                return dict(obj)
            except Exception:
                pass
        elif hasattr(obj, "__iter__"):
            return list(item for item in obj)
        return super(JSONEncoder, self).default(obj)


def dump_json(data, filepath):
    """Serialize ``data`` as a JSON formatted stream to ``filepath``"""
    kwargs = {
        "ensure_ascii": False,
        "indent": 2,
        "separators": (",", ": "),
        "cls": JSONEncoder,
    }
    with open(filepath, "w", encoding="utf-8") as fd:
        fd.write(json.dumps(data, **kwargs))


def load_json(filepath):
    """Deserialize ``filepath`` to a Python object."""
    with open(filepath, "r", encoding="utf-8") as fd:
        return json.load(fd)