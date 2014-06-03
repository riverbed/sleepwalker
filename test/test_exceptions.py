# Copyright (c) 2013-2014 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/sleepwalker/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

from sleepwalker import SleepwalkerException, HTTPError
import requests
import mock
import json
import pytest


# Most python exceptions behave like this, where the constructor
# takes arguments that __str__() recites.  SleepwalkerException
# simply inherits this behavior from Exception.
def test_sleepwalker_exception():
    xcls = SleepwalkerException
    xptn = xcls()
    assert str(xptn) == ''
    xptn = xcls('foo')
    assert str(xptn) == 'foo'
    xptn = xcls('foo', 2)
    assert xptn.args == ('foo', 2)
    assert str(xptn) == "('foo', 2)"
    assert repr(xptn) == "SleepwalkerException('foo', 2)"


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
    assert repr(exc) == "HTTPError(u'Malformed input structure',)"


# If it's not a GL5 response, make sure we get the HTTP error reason
def test_non_gl5_response():
    response = mock.Mock(requests.Response)
    response.status_code = 400
    response.reason = 'Bad Request'
    response.headers = {'content-type': 'application/json'}
    response.json = mock.Mock(return_value=None)
    exc = HTTPError(response)
    assert str(exc) == 'Bad Request'
    assert repr(exc) == "HTTPError('Bad Request',)"


# If some bits are missing, make sure we still get the HTTPError
def test_crippled_response():
    response = mock.Mock(requests.Response)
    response.status_code = 400
    response.headers = {'content-type': 'application/json'}
    response.json = mock.Mock(return_value=None)
    with pytest.raises(AttributeError):
        HTTPError(response)
