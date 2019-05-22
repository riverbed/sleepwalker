# Copyright (c) 2019 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

import sys
import json

import mock
import pytest
import requests

from sleepwalker import HTTPError, ClientHTTPError, ServerHTTPError

# Python 3.7 changes the repr of exceptions
# https://bugs.python.org/issue30399
PY37 = sys.version_info.major == 3 and sys.version_info.minor >= 7

# HTTPError's constructor takes a requests.Response argument,
# which it mines for a __str__() message, assuming that the
# response contains the conventional GL5 JSON error data.
def test_gl5_error_response():
    response = mock.Mock(requests.Response)
    response.status_code = 400
    response.reason = 'Bad Request'
    response.text = ('{"error_id": "REQUEST_INVALID_INPUT",'
                     ' "error_text": "Malformed input structure",'
                     ' "error_info": {"name": "2pac"}}')
    response.headers = {'content-type': 'application/json'}
    r_json = json.loads(response.text)
    response.json = mock.Mock(return_value=r_json)
    exc = HTTPError(response)
    assert str(exc) == 'Malformed input structure'

    if PY37:
        assert repr(exc) == "HTTPError('Malformed input structure')"
    else:
        assert repr(exc) == "HTTPError('Malformed input structure',)"


# If it's not a GL5 response, make sure we get the HTTP error reason
def test_non_gl5_response():
    response = mock.Mock(requests.Response)
    response.status_code = 400
    response.reason = 'Bad Request'
    response.headers = {'content-type': 'application/json'}
    response.json = mock.Mock(return_value=None)
    exc = HTTPError(response)
    assert str(exc) == 'Bad Request'

    if PY37:
        assert repr(exc) == "HTTPError('Bad Request')"
    else:
        assert repr(exc) == "HTTPError('Bad Request',)"


# If some bits are missing, make sure we still get the HTTPError
def test_crippled_response():
    response = mock.Mock(requests.Response)
    response.status_code = 400
    response.headers = {'content-type': 'application/json'}
    response.json = mock.Mock(return_value=None)
    with pytest.raises(AttributeError):
        HTTPError(response)


# Let's not egregiously typo the code map to the point where we
# use a class twice or use a base class.
def test_http_error_code_map():
    bases = set((HTTPError, ClientHTTPError, ServerHTTPError))
    assert not bases.intersection(HTTPError.code_map.values())

    assert len(HTTPError.code_map) == len(HTTPError.code_map.values())
