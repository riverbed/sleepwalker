# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import re
from collections import OrderedDict
import copy
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
ANY_DATA_SCHEMA_DICT = {
    'type': 'object',
    'properties': {
        'x': {'type': 'string'},
        'a': {'type': 'array', 'items': {'type': 'number'}}
    }
}
# jsonschema.Schema instances are too much effort to mock.
ANY_DATA_SCHEMA = reschema.jsonschema.Schema.parse(input=ANY_DATA_SCHEMA_DICT,
                                                   name='any',
                                                   api='/api/1.0/test')

# It is important that this be more than one level deep due to bugs involving
# whether the root is set properly after the first level, but otherwise the
# exact location of the fragment in the data is irrelevant.
ANY_FRAGMENT_PTR = '/a/2'
ANY_FRAGMENT_SCHEMA_DICT = {'type': 'number'}
ANY_FRAGMENT_SCHEMA = ANY_DATA_SCHEMA[ANY_FRAGMENT_PTR]
ANY_FRAGMENT_SUBSCRIPT = lambda dr: dr['a'][2]
ANY_FRAGMENT_SLICE = lambda dr: dr['a'][1:]

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
    js = mock.MagicMock(reschema.jsonschema.Object)()

    # We need to pass isinstance tests.
    js.__class__ = reschema.jsonschema.Object

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
def any_datarep(mock_service):
    return datarep.DataRep(mock_service, ANY_URI, jsonschema=ANY_DATA_SCHEMA)

@pytest.fixture
def any_datarep_fragment(mock_service, mock_jsonschema, any_datarep):
    return datarep.DataRep(fragment=ANY_FRAGMENT_PTR, root=any_datarep)

@pytest.fixture
def data_datarep(any_datarep):
    def side_effect():
        any_datarep._data = ANY_DATA
    any_datarep.pull = mock.Mock(side_effect=side_effect)
    return any_datarep

@pytest.fixture
def data_fragment(data_datarep):
    return datarep.DataRep(fragment=ANY_FRAGMENT_PTR, root=data_datarep)

@pytest.fixture
def empty_datarep(any_datarep):
    def side_effect():
        any_datarep._data = {}
    any_datarep.pull = mock.Mock(side_effect=side_effect)
    return any_datarep

@pytest.fixture
def false_fragment(data_fragment):
    data_fragment.data = 0
    return data_fragment

@pytest.fixture
def failed_datarep(any_datarep):
    def side_effect():
        any_datarep._data = datarep.DataRep.FAIL
    any_datarep.pull = mock.Mock(side_effect=side_effect)
    return any_datarep

@pytest.fixture
def failed_fragment(failed_datarep):
    return datarep.DataRep(fragment=ANY_FRAGMENT_PTR, root=failed_datarep)

@pytest.fixture
def deleted_datarep(any_datarep):
    def side_effect():
        any_datarep._data = datarep.DataRep.DELETED
    any_datarep.pull = mock.Mock(side_effect=side_effect)
    return any_datarep

@pytest.fixture
def deleted_fragment(deleted_datarep):
    return datarep.DataRep(fragment=ANY_FRAGMENT_PTR, root=deleted_datarep)

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

    with mock.patch('sleepwalker.datarep.DataRep.from_schema') as patched:
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
    with mock.patch('sleepwalker.datarep.DataRep.from_schema') as patched:
        schema.jsonschema.links = {'self': self_link}
        kwargs = ANY_ITEM_PATH_VARS.copy()
        kwargs.update(ANY_ITEM_PARAMS)
        dr = schema.bind(**kwargs)
        assert dr is not None
        patched.assert_called_once_with(schema.service, ANY_ITEM_PATH_RESOLVED,
                                        jsonschema=schema.jsonschema,
                                        params=ANY_ITEM_PARAMS)

def test_schema_bind_extra_kwargs(schema, self_link):
    with mock.patch('sleepwalker.datarep.DataRep.from_schema') as patched:
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
    assert dr.fragment is ''
    assert dr._data is datarep.DataRep.UNSET
    assert dr.params is None

    helper_check_links(dr, present=[], absent=['_getlink', '_setlink',
                                               '_createlink', '_deletelink'])
    assert dr.data_valid() is False
    assert dr.data_unset() is True

def test_datarep_instantiation_no_service(mock_jsonschema):
    with pytest.raises(TypeError):
        dr = datarep.DataRep(uri=ANY_URI, jsonschema=mock_jsonschema)

def test_datarep_instantiation_no_uri(mock_service, mock_jsonschema):
    with pytest.raises(TypeError):
        dr = datarep.DataRep(mock_service, jsonschema=mock_jsonschema)

def test_datarep_instantiation_no_jsonschema(mock_service):
    with pytest.raises(TypeError):
        dr = datarep.DataRep(mock_service, ANY_URI)

def test_datarep_instantiation_fragment_no_root(mock_service,
                                                  mock_jsonschema):
    with pytest.raises(FragmentError):
        dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema,
                             fragment=ANY_FRAGMENT_PTR)

def test_datarep_instantiation_root_no_fragment(mock_service, mock_jsonschema,
                                                any_datarep):
    with pytest.raises(FragmentError):
        dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema,
                             root=any_datarep)

def test_datarep_instantiation_fragment_service(any_datarep):
    with pytest.raises(FragmentError):
        datarep.DataRep(any_datarep.service, root=any_datarep,
                        fragment=ANY_FRAGMENT_PTR)

def test_datarep_instantiation_fragment_uri(any_datarep):
    with pytest.raises(FragmentError):
        datarep.DataRep(uri=ANY_URI, root=any_datarep,
                        fragment=ANY_FRAGMENT_PTR)

def test_datarep_instantiation_fragment_jsonschema(any_datarep):
    with pytest.raises(FragmentError):
        datarep.DataRep(jsonschema=any_datarep.jsonschema, root=any_datarep,
                        fragment=ANY_FRAGMENT_PTR)

def test_datarep_instantiation_fragment_data(any_datarep):
    with pytest.raises(FragmentError):
        datarep.DataRep(data=42, root=any_datarep, fragment=ANY_FRAGMENT_PTR)

def test_datarep_instantiation_fragment_params(any_datarep):
    with pytest.raises(FragmentError):
        datarep.DataRep(params={'x': 1}, root=any_datarep,
                        fragment=ANY_FRAGMENT_PTR)

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

# ================= valid/invalid ========================================

def test_datarep_valid(any_datarep):
    any_datarep._data = ANY_DATA
    assert any_datarep.data_valid()
    assert not any_datarep.data_unset()

def test_datarep_not_valid_undef(any_datarep):
    # This covers the undefined data case:
    assert not any_datarep.data_valid()
    assert any_datarep.data_unset()

def test_datarep_not_valid_fail(any_datarep):
    any_datarep._data = datarep.DataRep.FAIL
    assert not any_datarep.data_valid()
    assert not any_datarep.data_unset()
    with pytest.raises(DataPullError):
        any_datarep.data

def test_datarep_not_valid_deleted(any_datarep):
    any_datarep._data = datarep.DataRep.DELETED
    assert not any_datarep.data_valid()
    assert not any_datarep.data_unset()
    with pytest.raises(DataPullError):
        any_datarep.data

def test_datarep_fragment_valid(any_datarep_fragment):
    any_datarep_fragment.root._data = ANY_DATA
    assert any_datarep_fragment.data_valid()
    assert not any_datarep_fragment.data_unset()

def test_datarep_fragment_not_valid_undef(any_datarep_fragment):
    # This covers the undefined data case:
    assert not any_datarep_fragment.data_valid()
    assert any_datarep_fragment.data_unset()

def test_datarep_fragment_not_valid_fail(any_datarep_fragment):
    any_datarep_fragment.root._data = datarep.DataRep.FAIL
    assert not any_datarep_fragment.data_valid()
    assert not any_datarep_fragment.data_unset()
    with pytest.raises(DataPullError):
        any_datarep_fragment.data

def test_datarep_fragment_not_valid_deleted(any_datarep_fragment):
    # print any_datarep_fragment.jsonschema.fullname()
    any_datarep_fragment.root._data = datarep.DataRep.DELETED
    assert not any_datarep_fragment.data_valid()
    assert not any_datarep_fragment.data_unset()
    with pytest.raises(DataPullError):
        any_datarep_fragment.data

# ================= True/False  ========================================

@pytest.mark.bool
def test_datarep_with_true_data(data_datarep):
    assert data_datarep

@pytest.mark.bool
def test_fragment_with_true_datae(data_fragment):
    assert data_fragment

@pytest.mark.bool
def test_datarep_with_false_data(empty_datarep):
    assert not empty_datarep

@pytest.mark.bool
def test_fragment_with_false_data(false_fragment):
    assert not false_fragment

@pytest.mark.bool
def test_datarep_failed_false(failed_datarep):
    assert not failed_datarep

@pytest.mark.bool
def test_fragment_failed_false(failed_fragment):
    assert not failed_fragment

@pytest.mark.bool
def test_datarep_deleted_data_false(deleted_datarep):
    assert not deleted_datarep

@pytest.mark.bool
def test_fragment_deleted_data_false(deleted_fragment):
    assert not deleted_fragment

# ================= data, push, pull ========================================

def test_datarep_data_getter_first_access(any_datarep):
    def side_effect():
        any_datarep._data = ANY_DATA
    any_datarep.pull = mock.Mock(side_effect=side_effect)
    d = any_datarep.data
    any_datarep.pull.assert_called_once_with()
    assert d == ANY_DATA

def test_datarep_data_getter_first_access_fragment(any_datarep_fragment):
    def side_effect():
        any_datarep_fragment.root._data = ANY_DATA
    any_datarep_fragment.root.pull = mock.Mock(side_effect=side_effect)
    any_datarep_fragment.pull = mock.Mock()

    d = any_datarep_fragment.data

    assert not any_datarep_fragment.pull.called
    any_datarep_fragment.root.pull.assert_called_once_with()
    assert d == resolve_pointer(ANY_DATA, ANY_FRAGMENT_PTR)

def test_datarep_data_setter(any_datarep):
    any_datarep.pull = mock.Mock()
    any_datarep.data = ANY_DATA
    assert not any_datarep.pull.called
    assert any_datarep._data == ANY_DATA

def test_datarep_data_setter_fragment(mock_service):
    root_data = copy.deepcopy(ANY_DATA)
    fragment_data = copy.deepcopy(ANY_DATA)
    root = datarep.DataRep(mock_service, ANY_URI, ANY_DATA_SCHEMA,
                           data=root_data)
    fragment = datarep.DataRep(root=root, fragment=ANY_FRAGMENT_PTR)
    modified_data = set_pointer(ANY_DATA, ANY_FRAGMENT_PTR, 42, inplace=False)
    root.pull = mock.Mock()
    fragment.pull = mock.Mock()

    fragment.data = 42

    assert fragment._data is datarep.DataRep.FRAGMENT
    assert fragment.data == 42
    assert root.data == modified_data

    assert not root.pull.called
    assert not fragment.pull.called

def test_datarep_push_fragment(mock_service):
    root_data = copy.deepcopy(ANY_DATA)
    fragment_data = copy.deepcopy(ANY_DATA)
    root = datarep.DataRep(mock_service, ANY_URI, ANY_DATA_SCHEMA,
                           data=root_data)
    fragment = datarep.DataRep(root=root, fragment=ANY_FRAGMENT_PTR)
    modified_data = set_pointer(ANY_DATA, ANY_FRAGMENT_PTR, 42, inplace=False)
    root.push = mock.Mock()
    root.pull = mock.Mock()
    fragment.pull = mock.Mock()

    retval = fragment.push(42)

    assert fragment._data is datarep.DataRep.FRAGMENT
    assert fragment.data == 42
    assert root.data == modified_data

    assert retval is fragment
    root.push.assert_called_once_with()
    assert not root.pull.called
    assert not fragment.pull.called

def test_datarep_getitem(mock_service):
    root = datarep.DataRep.from_schema(service=mock_service,
                                       uri=ANY_URI,
                                       jsonschema=ANY_DATA_SCHEMA,
                                       data=ANY_DATA)

    fragment = ANY_FRAGMENT_SUBSCRIPT(root)
    assert fragment.jsonschema == root.jsonschema[ANY_FRAGMENT_PTR]
    assert fragment._data is datarep.DataRep.FRAGMENT
    assert fragment.data == resolve_pointer(root.data, ANY_FRAGMENT_PTR)
    assert fragment.root == root

def test_datarep_getitem_slice(mock_service):
    root = datarep.DataRep.from_schema(service=mock_service,
                                       uri=ANY_URI,
                                       jsonschema=ANY_DATA_SCHEMA,
                                       data=ANY_DATA)

    fragments = root['a'][1:]
    assert len(fragments) == 2
    for fragment, ptr in zip(fragments, ('/a/1', '/a/2')):
        assert fragment.jsonschema == root.jsonschema[ptr]
        assert fragment._data == datarep.DataRep.FRAGMENT
        assert fragment.data == resolve_pointer(root.data, ptr)
        assert fragment.root == root

@pytest.mark.xfail
def test_datarep_with_params_data_setter(mock_service, mock_jsonschema):
    dr = datarep.DataRep(mock_service, ANY_URI, mock_jsonschema,
                         params={'foo': 'bar'})

    # Parametrized DataReps are read-only.
    # TODO: Is TypeError right?  A read-only dict would raise this, but
    #       sometimes the DataRep type supports writing.
    with pytest.raises(TypeError):
        datarep.data = {'somevalue': 'doesntmatter'}

