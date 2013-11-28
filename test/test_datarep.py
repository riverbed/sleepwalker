# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import re
from collections import OrderedDict
import json

import mock
import pytest
from jsonpointer import resolve_pointer, set_pointer

import reschema.jsonschema
from sleepwalker import service, datarep
from sleepwalker.exceptions import (LinkError, InvalidParameter,
                                    MissingVar, RelationError,
                                    FragmentError, LinkError,
                                    DataPullError, DataNotSetError)

ANY_URI = 'http://hostname.nbttech.com'
ANY_DATA = {'x': 'y', 'a': [1, 2, 3]}
ANY_FRAGMENT_PTR = '/a/2'

ANY_CONTAINER_PATH = '/foos'
ANY_CONTAINER_PARAMS_SCHEMA = {'filter': {'type': 'string'},
                               'other': {'type': 'number'}}
ANY_CONTAINER_PARAMS = {'filter': 'bar'}

ANY_ITEM_PATH_TEMPLATE = '/foos/items/{id}'
ANY_ITEM_PATH_VARS = {'id': 42}
ANY_ITEM_PATH_RESOLVED = '/foos/items/42'
ANY_ITEM_PARAMS_SCHEMA = {'timezone': {'type': 'string'}}
ANY_ITEM_PARAMS = {'timezone': 'PST'}

@pytest.fixture
def mock_service():
    return mock.Mock(service.Service)()

@pytest.fixture
def mock_jsonschema():
    js = mock.Mock(reschema.jsonschema.Schema)()

    # The links member almost always needs to exist and an iterable,
    # so set it to an empty object of the correct type by default.
    js.links = OrderedDict()

    # Set a "fullname" so that DataRep.__repr__ doesn't freak out
    # when it tries to use the mocked Schema in a string.
    js.fullname = mock.Mock(return_value='fullname')
    return js

@pytest.fixture
def schema(mock_service, mock_jsonschema):
    return datarep.Schema(mock_service, mock_jsonschema)
    
@pytest.fixture
def any_datarep(mock_service, mock_jsonschema):
    return datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)

@pytest.fixture
def any_datarep_fragment(mock_service, mock_jsonschema, any_datarep):
    return datarep.DataRep(mock_service, ANY_URI,
                           jsonschema=mock_jsonschema,
                           fragment=ANY_FRAGMENT_PTR,
                           parent=any_datarep)

# ============ Schema tests ============================
def test_schema_instantiation(mock_service, mock_jsonschema):
    schema = datarep.Schema(mock_service, mock_jsonschema)
    assert schema.service is mock_service
    assert schema.jsonschema is mock_jsonschema

def test_schema_bind_no_self(schema):
    with pytest.raises(LinkError):
        schema.bind()

def test_schema_bind_params_no_vars(schema):
    self_link = mock.Mock(reschema.jsonschema.Link)()
    self_link.path = mock.Mock(reschema.jsonschema.Path)()
    self_link.path.template = ANY_CONTAINER_PATH
    self_link.path.resolve.return_value = ANY_CONTAINER_PATH
    self_link._params = ANY_CONTAINER_PARAMS_SCHEMA

    with mock.patch('sleepwalker.datarep.DataRep') as patched:
        schema.jsonschema.links = {'self': self_link}
        dr = schema.bind(**ANY_CONTAINER_PARAMS)
        assert dr is not None
        patched.assert_called_once_with(schema.service, ANY_CONTAINER_PATH,
                                        jsonschema=schema.jsonschema,
                                        params=ANY_CONTAINER_PARAMS)

@pytest.fixture
def self_link():
    self_link = mock.Mock(reschema.jsonschema.Link)()
    self_link.path = mock.Mock(reschema.jsonschema.Path)()
    self_link.path.template = ANY_ITEM_PATH_TEMPLATE
    self_link.path.resolve.return_value = ANY_ITEM_PATH_RESOLVED
    self_link._params = ANY_ITEM_PARAMS_SCHEMA
    return self_link

def test_schema_bind_params_and_vars(schema, self_link):
    with mock.patch('sleepwalker.datarep.DataRep') as patched:
        schema.jsonschema.links = {'self': self_link}
        kwargs = ANY_ITEM_PATH_VARS.copy()
        kwargs.update(ANY_ITEM_PARAMS)
        dr = schema.bind(**kwargs)
        assert dr is not None
        patched.assert_called_once_with(schema.service, ANY_ITEM_PATH_RESOLVED,
                                        jsonschema=schema.jsonschema,
                                        params=ANY_ITEM_PARAMS)

def test_schema_bind_extra_kwargs(schema, self_link):
    with mock.patch('sleepwalker.datarep.DataRep') as patched:
        schema.jsonschema.links = {'self': self_link}
        kwargs = ANY_ITEM_PATH_VARS.copy()
        kwargs.update(ANY_ITEM_PARAMS)
        kwargs['garbage'] = -1
        with pytest.raises(InvalidParameter):
            schema.bind(**kwargs)

def test_schema_bind_missing_var(schema, self_link):
    with mock.patch('sleepwalker.datarep.DataRep') as patched:
        schema.jsonschema.links = {'self': self_link}
        with pytest.raises(MissingVar):
            schema.bind(thisiswrong='whatever')

    self_link = mock.Mock(reschema.jsonschema.Link)()
    self_link = mock.Mock(reschema.jsonschema.Link)()
    self_link.path = mock.Mock(reschema.jsonschema.Path)()
    self_link.path.template = ANY_ITEM_PATH_TEMPLATE
    self_link._params = {'thisiswrong': 'whocares'}

# ============ _DataRepValue tests ============================

def test_datarep_value():
    drv = datarep._DataRepValue('anylabel')
    assert drv.label == 'anylabel'


# ================== DataRep tests ============================

def helper_check_links(dr, present, absent):
    for link_attr in present:
        assert getattr(dr, link_attr) is True
    for link_attr in absent:
        value = getattr(dr, link_attr)
        assert re.match(r"No '\w+' link for this resource$", value)

def test_datarep_instantiation_defaults(mock_service, mock_jsonschema):
    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)

    assert dr.service is mock_service
    assert dr.uri is ANY_URI
    assert dr.jsonschema is mock_jsonschema
    assert dr.fragment is None
    assert dr._data is datarep.DataRep.UNSET
    assert dr.params is None

    helper_check_links(dr, present=[], absent=['_getlink', '_setlink',
                                               '_createlink', '_deletelink'])
    assert dr.data_valid() is False
    assert dr.data_unset() is True

def test_datarep_instantiation_fragment_no_parent(mock_service,
                                                  mock_jsonschema):
    with pytest.raises(FragmentError):
        dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema,
                             fragment=ANY_FRAGMENT_PTR)

def test_datarep_instantiation_parent_no_fragment(mock_service, mock_jsonschema,
                                                  any_datarep):
    with pytest.raises(FragmentError):
        dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema,
                             parent=any_datarep)

def test_datarep_instantiation_empty_params(mock_service, mock_jsonschema):
    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema,
                         params={})
    assert dr.params is None

def test_datarep_with_get(mock_service, mock_jsonschema):
    mock_jsonschema.links['get'] = mock.Mock(reschema.jsonschema.Link)()
    mock_jsonschema.matches = mock.Mock(return_value=True)

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=['_getlink'],
                           absent=['_setlink', '_createlink', '_deletelink'])

def test_datarep_with_get_invalid_response(mock_service, mock_jsonschema):
    mock_jsonschema.links['get'] = mock.Mock(reschema.jsonschema.Link)()
    mock_jsonschema.matches = mock.Mock(return_value=False)

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=[], absent=['_setlink',
                                               '_createlink', '_deletelink'])
    assert 'response does not match:' in dr._getlink

def test_datarep_with_set(mock_service, mock_jsonschema):
    mock_jsonschema.links['set'] = mock.Mock(reschema.jsonschema.Link)()
    mock_jsonschema.matches = mock.Mock(return_value=True)

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=['_setlink'],
                           absent=['_getlink', '_createlink', '_deletelink'])

def test_datarep_with_set_invalid_request(mock_service, mock_jsonschema):
    mock_jsonschema.links['set'] = mock.Mock(reschema.jsonschema.Link)()

    # side_effect's result is used as the return value, and this
    # sets side_effect to a generator returning first False and then True.
    mock_jsonschema.matches = mock.Mock(side_effect=(x for x in (False, True)))

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=[], absent=['_getlink',
                                               '_createlink', '_deletelink'])
    assert "'set' link request does not match schema" == dr._setlink

def test_datarep_with_set_invalid_response(mock_service, mock_jsonschema):
    mock_jsonschema.links['set'] = mock.Mock(reschema.jsonschema.Link)()
    mock_jsonschema.matches = mock.Mock(side_effect=(x for x in (True, False)))

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=[], absent=['_getlink',
                                               '_createlink', '_deletelink'])
    assert "'set' link response does not match schema" == dr._setlink

def test_datarep_with_create(mock_service, mock_jsonschema):
    mock_jsonschema.links['create'] = mock.Mock(reschema.jsonschema.Link)()
    mock_jsonschema.links['create'].request.matches = \
      mock.Mock(return_value=True)

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=['_createlink'],
                           absent=['_getlink', '_setlink', '_deletelink'])

def test_datarep_with_create_req_resp_not_match(mock_service, mock_jsonschema):
    mock_jsonschema.links['create'] = mock.Mock(reschema.jsonschema.Link)()
    mock_jsonschema.links['create'].request.matches = \
      mock.Mock(return_value=False)

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=[], absent=['_getlink', '_setlink',
                                               '_deletelink'])
    assert 'request does not match the response' in dr._createlink

def test_datarep_with_delete(mock_service, mock_jsonschema):
    mock_jsonschema.links['delete'] = mock.Mock(reschema.jsonschema.Link)()
    mock_jsonschema.matches = mock.Mock(return_value=True)

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=['_deletelink'],
                           absent=['_getlink', '_setlink', '_createlink'])

def test_datarep_data_getter_first_access(any_datarep):
    def side_effect():
        any_datarep._data = ANY_DATA
    any_datarep.pull = mock.Mock(side_effect=side_effect)
    d = any_datarep.data
    any_datarep.pull.assert_called_once_with()
    assert d == ANY_DATA

def test_datarep_data_getter_first_access_fragment(any_datarep_fragment):
    def side_effect():
        any_datarep_fragment._data = ANY_DATA
    any_datarep_fragment.pull = mock.Mock(side_effect=side_effect)
    d = any_datarep_fragment.data
    any_datarep_fragment.pull.assert_called_once_with()
    assert d == resolve_pointer(ANY_DATA, ANY_FRAGMENT_PTR)

