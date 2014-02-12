# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

from collections import OrderedDict

import mock
import pytest

from sleepwalker import service, connection
from sleepwalker.exceptions import (ServiceException, ResourceException,
                                    TypeException)
from reschema import servicedef

ANY_HOSTNAME = 'http://hostname.nbttech.com'
ANY_AUTH = ('username', 'password')
ANY_PORT = 1234
NON_DEFAULT_VERIFY = False

ANY_BIND_KWARGS = {'foo': 'bar', 'x': 1}

ANY_SCHEMA_FILENAME = 'any_schema.yml'
ANY_TYPE_NAME = 'any_type_name'
ANY_RESOURCE_NAME = 'any_resource_name'
ANY_RESOURCE_JSONSCHEMA = OrderedDict({ANY_RESOURCE_NAME: {}})
ANY_RESOURCE_LOOKUP_FUNCTION = mock.MagicMock(
                                 return_value=ANY_RESOURCE_JSONSCHEMA)
# This exception needs to be specific to sleepwalker.
ANY_RESOURCE_LOOKUP_EXCEPTION = ResourceException

@pytest.fixture
def any_service():
    return service.Service()

def test_service_instantiation(any_service):
    assert any_service.connection is None
    assert any_service.servicedef is None

def test_add_connection_defaults(any_service):
    with mock.patch('sleepwalker.service.Connection') as patched:
        mock_conn = patched.return_value
        any_service.add_connection(ANY_HOSTNAME)
        patched.assert_called_once_with(ANY_HOSTNAME, None, None, True)
        assert any_service.connection is mock_conn

def test_add_connection_non_defaults(any_service):
    with mock.patch('sleepwalker.service.Connection') as patched:
        mock_conn = patched.return_value
        any_service.add_connection(ANY_HOSTNAME, auth=ANY_AUTH,
                                                 port=ANY_PORT,
                                                 verify=NON_DEFAULT_VERIFY)
        patched.assert_called_once_with(ANY_HOSTNAME, ANY_AUTH, ANY_PORT,
                                                      NON_DEFAULT_VERIFY)
        assert any_service.connection is mock_conn

def test_response_no_connection(any_service):
    assert any_service.response is None

def test_response_no_response(any_service):
    any_service.connection = mock.MagicMock(return_value=None)
    any_service.connection.response = None
    assert any_service.response is None

# fetch_servicedef() currently doesn't do anything,
# and the details of what it should do are unclear as noted in a comment.
@pytest.mark.xfail
def test_fetch_servicedef_initial(any_service):
    with mock.patch('sleepwalker.service.Servicedef') as patched:
        any_service.fetch_servicedef()
        mock_servicedef = patched.return_value
        assert any_service.servicedef is mock_servicedef

def test_load_servicedef(any_service):
    with mock.patch('sleepwalker.service.ServiceDef') as patched:
        mock_servicedef = patched.return_value
        any_service.load_servicedef(ANY_SCHEMA_FILENAME)
        assert any_service.servicedef is mock_servicedef
        any_service.servicedef.load.assert_called_once_with(ANY_SCHEMA_FILENAME)

def test_service_bind_no_schema(any_service):
    with pytest.raises(ServiceException):
        any_service.bind(ANY_RESOURCE_NAME)

def test_service_bind(any_service):
    with mock.patch('sleepwalker.service.ServiceDef') as patched_servicedef:
        with mock.patch('sleepwalker.service.Schema') as patched_schema:
            empty_dict = OrderedDict()
            mock_servicedef = patched_servicedef.return_value
            mock_servicedef.find_resource = mock.Mock(return_value=empty_dict)
            mock_schema = patched_schema.return_value

            any_service.load_servicedef(ANY_SCHEMA_FILENAME)
            any_service.bind(ANY_RESOURCE_NAME)
            mock_schema.bind.assert_called_with()

            any_service.bind(ANY_RESOURCE_NAME, **ANY_BIND_KWARGS)
            mock_schema.bind.assert_called_with(**ANY_BIND_KWARGS)

def test__lookup_no_schema(any_service):
    with pytest.raises(ServiceException):
        any_service._lookup(ANY_RESOURCE_NAME,
                            ANY_RESOURCE_LOOKUP_FUNCTION,
                            ANY_RESOURCE_LOOKUP_EXCEPTION)

def test__lookup_cant_find_name(any_service):
    with mock.patch('sleepwalker.service.ServiceDef'):
        any_service.load_servicedef(ANY_SCHEMA_FILENAME)
        mock_lookup_keyerror = mock.Mock(side_effect=KeyError)
        with pytest.raises(ANY_RESOURCE_LOOKUP_EXCEPTION):
            any_service._lookup(ANY_RESOURCE_NAME, mock_lookup_keyerror,
                                ANY_RESOURCE_LOOKUP_EXCEPTION)

def test__lookup_success(any_service):
    with mock.patch('sleepwalker.service.ServiceDef'):
        any_service.load_servicedef(ANY_SCHEMA_FILENAME)
        with mock.patch('sleepwalker.service.Schema') as patched_schema:
            mock_schema = patched_schema.return_value
            schema = any_service._lookup(ANY_RESOURCE_NAME,
                                         ANY_RESOURCE_LOOKUP_FUNCTION,
                                         ANY_RESOURCE_LOOKUP_EXCEPTION)
            assert schema is mock_schema
            patched_schema.assert_called_with(any_service,
                                              ANY_RESOURCE_JSONSCHEMA)

def test_lookup_resource(any_service):
    any_service._lookup = mock.Mock()
    any_service.servicedef = mock.Mock(servicedef.ServiceDef)
    any_service.servicedef.find_resource = mock.Mock(return_value=OrderedDict())
    any_service.lookup_resource(ANY_RESOURCE_NAME)
    any_service._lookup.assert_called_once_with(
      ANY_RESOURCE_NAME,
      any_service.servicedef.find_resource,
      ResourceException)

def test_lookup_type(any_service):
    any_service._lookup = mock.Mock()
    any_service.servicedef = mock.Mock(servicedef.ServiceDef)
    any_service.servicedef.find_type = mock.Mock(return_value=OrderedDict())
    any_service.lookup_type(ANY_TYPE_NAME)
    any_service._lookup.assert_called_once_with(
      ANY_TYPE_NAME,
      any_service.servicedef.find_type,
      TypeException)

