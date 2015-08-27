# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

import re
from collections import OrderedDict, namedtuple
import copy
import json
import requests
import requests_mock
import mock
import pytest
from jsonpointer import resolve_pointer, set_pointer

import reschema.jsonschema
import reschema.exceptions
from sleepwalker import service, datarep, connection
from sleepwalker.exceptions import \
    LinkError, InvalidParameter, MissingVariable, FragmentError, \
    DataPullError, HTTPError, HTTPNotFound

ANY_URI = 'http://hostname.nbttech.com'
ANY_DATA = {
    'x': 'y',
    'a': [1, 2, 3],
    'b': [
        {
            # oneOf object or array.
            'c': [
                {'e': 4},
                [5, 6]
            ],
            'd': [],
        }
    ],
}

ANY_DATA_SCHEMA_DICT = {
    'type': 'object',
    'properties': {
        'x': {'type': 'string'},
        'a': {'type': 'array', 'items': {'type': 'number'}},
        'b': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'array',
                    'items': {
                        'oneOf': [
                            {'type': 'object',
                             'additionalProperties': {'type': 'number'}},
                            {'type': 'array', 'items': {'type': 'number'}}
                        ],
                    },
                },
            },
        },
    },
    'links': {'self': {'path': '$/anything'}},
}

MERGE_TARGET_DESC = 'Description before merge'
MERGE_WITH_DESC = 'Description after merge'

ANY_SERVICE_DEF_TEXT = {
    '$schema': 'http://support.riverbed.com/apis/service_def/2.2',
    'id': 'http://support.riverbed.com/apis/unittest/1.0',
    'provider': 'riverbed',
    'name': 'unittest',
    'version': '1.0',
    'title': 'API for use in unit tests',
    'defaultAuthorization': 'none',
    'types': {
        'merge_target': {
            'type': 'object',
            'properties': {
                'obj': {'type': 'object', 'additionalProperties': False},
                'arr': {'type': 'array', 'items': {'type': 'number'}},
                'i': {'type': 'integer'},
            },
            'description': MERGE_TARGET_DESC,
        },
    },
    'resources': {
        'referenced': {
            'type': 'object',
            'properties': {
                'thing': {'type': 'array', 'items': {'type': 'number'}},
            },
            'links': {
                'self': {'path': '$/whatever'},
                'get': {
                    'method': 'GET',
                    'request': {'$ref': '#/resources/referenced'},
                    'response': {'$ref': '#/resources/referenced'},
                },
            },
        },
        'referencing': {
            'type': 'object',
            'properties': {
                'reference': {'$ref': '#/resources/referenced'},
            },
            'links': {
                'self': {'path': '$/notimportant'},
                'get': {
                    'method': 'GET',
                    'request': {'$ref': '#/resources/referenced'},
                    'response': {'$ref': '#/resources/referenced'},
                },
            },
        },
        'merged': {
            '$merge': {
                'source': {'$ref': '#/types/merge_target'},
                'with': {
                    'description': MERGE_WITH_DESC,
                    'links': {
                        'self': {'path': '$/whatever'},
                    },
                },
            },
        },
    },
}

ANY_SERVICE_DATA = {
    'referenced': {'thing': [1, 2, 3]},
    'referencing': {'reference': {'thing': [10, 20]}},
    'merged': {'obj': {}, 'arr': [0, 1, 2], 'i': 42}
}

ANY_SERVICE_PATH = '/apis/foo/1.0'

# jsonschema.Schema instances are too much effort to mock.
ANY_SERVICE_DEF = reschema.ServiceDef()
ANY_SERVICE_DEF.parse(ANY_SERVICE_DEF_TEXT)
ANY_DATA_SCHEMA = reschema.jsonschema.Schema.parse(input=ANY_DATA_SCHEMA_DICT,
                                                   name='any',
                                                   servicedef=ANY_SERVICE_DEF)

# It is important that this be more than one level deep due to bugs involving
# whether the root is set properly after the first level, but otherwise the
# exact location of the fragment in the data is irrelevant.
ANY_FRAGMENT_PTR = '/a/2'
ANY_FRAGMENT_SCHEMA_DICT = {'type': 'number'}
ANY_FRAGMENT_SCHEMA = ANY_DATA_SCHEMA.by_pointer(ANY_FRAGMENT_PTR)

ANY_CONTAINER_PATH = '$/foos'
ANY_CONTAINER_PARAMS_SCHEMA = {'filter': {'type': 'string'},
                               'other': {'type': 'number'}}
ANY_CONTAINER_PARAMS = {'filter': 'bar'}

ANY_ITEM_PATH_TEMPLATE = '$/foos/items/{id}{?timezone}'
ANY_ITEM_PATH_VARS = {'id': 42}
ANY_ITEM_PATH_RESOLVED = '$/foos/items/42'
ANY_ITEM_PARAMS_SCHEMA = {'timezone': {'type': 'string'}}
ANY_ITEM_PARAMS = {'timezone': 'PST'}

STRICT_SCHEMA_DICT = {
    '$schema': 'http://support.riverbed.com/apis/service_def/2.2',
    'id': 'http://whatever.com',
    'provider': 'riverbed',
    'name': 'validate_me',
    'version': '1.0',
    'resources': {
        'anything': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': {'type': 'number'},
                'value': {'type': 'string'},
            },
            'links': {
                'self': {'path': '$/anything/{id}'},
                'get': {
                    'method': 'GET',
                    'response': {'$ref': '#/resources/anything'}
                },
                'create': {
                    'method': 'POST',
                    'request': {'$ref': '#/resources/anything'},
                    'response': {'$ref': '#/resources/anything'}
                },
                'set': {
                    'method': 'PUT',
                    'request': {'$ref': '#/resources/anything'},
                    'response': {'$ref': '#/resources/anything'}
                },
                'delete': {
                    'method': 'DELETE',
                    'response': {
                        'type': 'object',
                        'properties': {
                            'status': {
                                'type': 'number',
                                'enum': [200, 204]
                            }
                        }
                    }
                }
            },
        },
    },
}


@pytest.yield_fixture
def validate_response():
    '''Confirm VALIDATE_RESPONSE is True for testing, then restore original.
    '''
    original_validate_setting = datarep.VALIDATE_RESPONSE
    datarep.VALIDATE_RESPONSE = True
    yield  # ...while test runs
    datarep.VALIDATE_RESPONSE = original_validate_setting


@pytest.fixture
def mock_datarep():
    conn = connection.Connection(ANY_URI)
    svcdef = reschema.ServiceDef()
    svcdef.parse(STRICT_SCHEMA_DICT)
    svc = service.Service(svcdef, ANY_URI, connection=conn)
    mock_dr = svc.bind('anything', id=42)
    return mock_dr


@pytest.fixture
def ref_pair_datareps(mock_service):
    rs = ANY_SERVICE_DEF

    pair = namedtuple('referenced', 'referencing')
    pair.referenced = datarep.DataRep.from_schema(
        service=mock_service,
        uri=ANY_URI,
        jsonschema=rs.resources['referenced'])
    pair.referencing = datarep.DataRep.from_schema(
        service=mock_service,
        uri=ANY_URI,
        jsonschema=rs.resources['referencing'])

    def referenced_data():
        pair.referenced._data = ANY_SERVICE_DATA['referenced']
    pair.referenced.pull = mock.Mock(side_effect=referenced_data)

    def referencing_data():
        pair.referencing._data = ANY_SERVICE_DATA['referencing']
    pair.referencing.pull = mock.Mock(side_effect=referencing_data)

    return pair


@pytest.fixture
def merged_datarep(mock_service):
    rs = ANY_SERVICE_DEF
    merged = datarep.DataRep.from_schema(
        service=mock_service,
        uri=ANY_URI,
        jsonschema=rs.resources['merged'])

    def referenced_data():
        merged._data = ANY_SERVICE_DATA['merged']
    merged.pull = mock.Mock(side_effect=referenced_data)

    return merged


@pytest.fixture
def mock_service():
    svc = mock.MagicMock(service.Service)()

    # servicepath needs to be a string
    svc.servicepath = ANY_SERVICE_PATH

    return svc


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
    return datarep.DataRep.from_schema(mock_service, ANY_URI,
                                       jsonschema=ANY_DATA_SCHEMA)


@pytest.fixture
def any_datarep_fragment(mock_service, mock_jsonschema, any_datarep):
    return datarep.DataRep.from_schema(fragment=ANY_FRAGMENT_PTR,
                                       root=any_datarep)


@pytest.fixture
def any_datarep_with_object_data(mock_service):
    return datarep.DataRep.from_schema(mock_service, ANY_URI,
                                       jsonschema=ANY_DATA_SCHEMA,
                                       data=ANY_DATA)


@pytest.fixture
def any_datarep_fragment_with_array_data(any_datarep_with_object_data):
    return any_datarep_with_object_data['a']


@pytest.fixture
def data_datarep(any_datarep):
    def side_effect():
        any_datarep._data = ANY_DATA
    any_datarep.pull = mock.Mock(side_effect=side_effect)
    return any_datarep


@pytest.fixture
def data_fragment(data_datarep):
    return datarep.DataRep.from_schema(fragment=ANY_FRAGMENT_PTR,
                                       root=data_datarep)


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
    return datarep.DataRep.from_schema(fragment=ANY_FRAGMENT_PTR,
                                       root=failed_datarep)


@pytest.fixture
def deleted_datarep(any_datarep):
    def side_effect():
        any_datarep._data = datarep.DataRep.DELETED
    any_datarep.pull = mock.Mock(side_effect=side_effect)
    return any_datarep


@pytest.fixture
def deleted_fragment(deleted_datarep):
    return datarep.DataRep.from_schema(fragment=ANY_FRAGMENT_PTR,
                                       root=deleted_datarep)


# ============ Schema tests ============================
def test_schema_instantiation(mock_service, mock_jsonschema):
    schema = datarep.Schema(mock_service, mock_jsonschema)
    assert schema.service is mock_service
    assert schema.jsonschema is mock_jsonschema


def test_schema_bind_no_self(schema):
    with pytest.raises(LinkError):
        schema.bind()


@pytest.fixture
def self_link():
    self_link = mock.Mock(reschema.jsonschema.Link)()
    self_link.path = mock.Mock(reschema.jsonschema.Path)()
    self_link.path.template = ANY_ITEM_PATH_TEMPLATE
    self_link.path.resolve.return_value = (ANY_ITEM_PATH_RESOLVED, {})
    self_link.path.vars = ANY_ITEM_PARAMS_SCHEMA
    return self_link


def test_schema_bind_params_and_vars(schema, self_link):
    with mock.patch('sleepwalker.datarep.DataRep.from_schema') as patched:
        schema.jsonschema.links = {'self': self_link}
        kwargs = ANY_ITEM_PATH_VARS.copy()
        kwargs.update(ANY_ITEM_PARAMS)
        dr = schema.bind(**kwargs)
        assert dr is not None
        patched.assert_called_once_with(
            schema.service, ANY_SERVICE_PATH + ANY_ITEM_PATH_RESOLVED[1:],
            jsonschema=schema.jsonschema)


def test_schema_bind_extra_kwargs(schema, self_link):
    with mock.patch('sleepwalker.datarep.DataRep.from_schema'):
        schema.jsonschema.links = {'self': self_link}
        kwargs = ANY_ITEM_PATH_VARS.copy()
        kwargs.update(ANY_ITEM_PARAMS)
        kwargs['garbage'] = -1
        with pytest.raises(InvalidParameter):
            schema.bind(**kwargs)


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

    helper_check_links(dr, present=[], absent=['_getlink', '_setlink',
                                               '_createlink', '_deletelink'])
    assert dr.data_valid() is False
    assert dr.data_unset() is True


def test_datarep_instantiation_no_service(mock_jsonschema):
    with pytest.raises(TypeError):
        datarep.DataRep(uri=ANY_URI, jsonschema=mock_jsonschema)


def test_datarep_instantiation_no_uri(mock_service, mock_jsonschema):
    with pytest.raises(TypeError):
        datarep.DataRep(mock_service, jsonschema=mock_jsonschema)


def test_datarep_instantiation_no_jsonschema(mock_service):
    with pytest.raises(TypeError):
        datarep.DataRep(mock_service, ANY_URI)


def test_datarep_instantiation_fragment_no_root(mock_service,
                                                mock_jsonschema):
    with pytest.raises(FragmentError):
        datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema,
                        fragment=ANY_FRAGMENT_PTR)


def test_datarep_instantiation_root_no_fragment(mock_service, mock_jsonschema,
                                                any_datarep):
    with pytest.raises(FragmentError):
        datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema,
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


@pytest.mark.xfail
def test_datarep_instantiation_fragment_params(any_datarep):
    with pytest.raises(FragmentError):
        datarep.DataRep(params={'x': 1}, root=any_datarep,
                        fragment=ANY_FRAGMENT_PTR)


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
    mock_jsonschema.links['create'].request.links = \
        {'self': mock.Mock(reschema.jsonschema.Link)()}
    mock_jsonschema.links['create'].request.matches = \
        mock.Mock(return_value=True)

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=['_createlink'],
                       absent=['_getlink', '_setlink', '_deletelink'])


def test_datarep_with_create_req_resp_not_match(mock_service, mock_jsonschema):
    mock_jsonschema.links['create'] = mock.Mock(reschema.jsonschema.Link)()
    mock_jsonschema.links['create'].request.links = \
        {'self': mock.Mock(reschema.jsonschema.Link)()}
    mock_jsonschema.links['create'].request.matches = \
        mock.Mock(return_value=False)

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=[], absent=['_getlink', '_setlink',
                                               '_deletelink'])
    assert 'request does not match the response' in dr._createlink


def test_datarep_with_create_req_not_resource(mock_service, mock_jsonschema):
    mock_jsonschema.links['create'] = mock.Mock(reschema.jsonschema.Link)()
    mock_jsonschema.links['create'].request.links = {}

    dr = datarep.DataRep(mock_service, ANY_URI, jsonschema=mock_jsonschema)
    helper_check_links(dr, present=[], absent=['_getlink', '_setlink',
                                               '_deletelink'])
    assert 'request is not a resource' in dr._createlink


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
    with pytest.raises(DataPullError):
        bool(failed_datarep)
    assert failed_datarep._data is datarep.DataRep.FAIL


@pytest.mark.bool
def test_fragment_failed_false(failed_fragment):
    with pytest.raises(DataPullError):
        bool(failed_fragment)
    assert failed_fragment.root._data is datarep.DataRep.FAIL


@pytest.mark.bool
def test_datarep_deleted_data_false(deleted_datarep):
    with pytest.raises(DataPullError):
        bool(deleted_datarep)
    assert deleted_datarep._data is datarep.DataRep.DELETED


@pytest.mark.bool
def test_fragment_deleted_data_false(deleted_fragment):
    with pytest.raises(DataPullError):
        bool(deleted_fragment)
    assert deleted_fragment.root._data is datarep.DataRep.DELETED


# ================= URL parameters ==========================================

@pytest.mark.xfail
def test_apply_params(data_datarep):
    # Pull to ensure that we have data that is not propagated.
    data_datarep.pull()

    with_params = data_datarep.apply_params(foo=1, bar="hello world")
    assert with_params.params == {'foo': 1, 'bar': 'hello world'}
    assert with_params._data is datarep.DataRep.UNSET

    assert data_datarep.uri == with_params.uri
    assert data_datarep.jsonschema is with_params.jsonschema
    assert data_datarep.service is with_params.service
    assert data_datarep.root is with_params.root
    assert data_datarep.fragment == with_params.fragment

    other_params = with_params.apply_params(more='stuff')
    assert other_params.params == {'more': 'stuff'}
    assert other_params._data is datarep.DataRep.UNSET

    no_params = other_params.apply_params()
    assert no_params.params is None
    assert other_params._data is datarep.DataRep.UNSET


def test_apply_params_to_fragment(data_fragment):
    with pytest.raises(NotImplementedError):
        data_fragment.apply_params()


# ================= data, push, pull ========================================

def test_pull_no_validation_with_valid_data(mock_datarep):
    '''Confirm valid pull() with valid data and VALIDATE_RESPONSE == False
    '''
    return_data = {'id': 42, 'value': 'foobar'}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.get(svc_path, json=return_data)
        assert mock_datarep.pull().data == return_data


def test_pull_validation_with_valid_data(mock_datarep, validate_response):
    '''Confirm valid pull() with valid data and VALIDATE_RESPONSE == True
    '''
    return_data = {'id': 42, 'value': 'foobar'}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.get(svc_path, json=return_data)
        assert mock_datarep.pull().data == return_data


def test_pull_no_validation_with_invalid_data(mock_datarep):
    '''Confirm valid pull() with invalid data and VALIDATE_RESPONSE == False
    '''
    return_data = {'id': 42, 'value': 'foobar', 'extraneous': 123}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.get(svc_path, json=return_data)
        assert mock_datarep.pull().data == return_data


def test_pull_validation_with_invalid_data(mock_datarep, validate_response):
    '''Confirm reschema raises a ValidationError on pull() with invalid data
       and VALIDATE_RESPONSE == True
    '''
    return_data = {'id': 42, 'value': 'foobar', 'extraneous': 123}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.get(svc_path, json=return_data)

        with pytest.raises(reschema.exceptions.ValidationError):
            mock_datarep.pull()


def test_push_validation_with_valid_response(mock_datarep, validate_response):
    '''Confirm no error is raised on push() with valid response and
       VALIDATE_RESPONSE == True
    '''
    data = {'id': 42, 'value': 'foobar'}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.put(svc_path, json=data)
        assert mock_datarep.push(data).data == data


def test_push_validation_with_invalid_resp(mock_datarep, validate_response):
    '''Confirm reschema raises a ValidationError on push() when an
       invalid response is received and VALIDATE_RESPONSE == True
    '''
    data = {'id': 42, 'value': 'foobar'}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.put(svc_path, json={'status': 401})

        with pytest.raises(reschema.exceptions.ValidationError):
            mock_datarep.push(data)


def test_push_no_validation_with_invalid_resp(mock_datarep):
    '''Confirm reschema ignores an invalid response when
       VALIDATE_RESPONSE == False
    '''
    data = {'id': 42, 'value': 'foobar'}
    invalid_response = {'status': 401}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.put(svc_path, json=invalid_response)
        assert mock_datarep.push(data).data == invalid_response


def test_create_validation_with_valid_resp(mock_datarep, validate_response):
    '''Confirm reschema ignores an invalid response when
       VALIDATE_RESPONSE == False
    '''
    create_data = {'id': 42, 'value': 'foo'}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.post(svc_path, json=create_data)
        assert mock_datarep.create(create_data).data == create_data


def test_create_validation_with_invalid_resp(mock_datarep, validate_response):
    '''When VALIDATE_RESPONSE == True, confirm that reschema raises a
       ValidationError on create() if an invalid response is received
    '''
    data = {'value': 'foobar'}
    invalid_response = {'id': 42, 'value': 'foo', 'extra_thing': 'foo'}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.post(svc_path, json=invalid_response)

        with pytest.raises(reschema.exceptions.ValidationError):
            mock_datarep.create(data)


def test_create_with_invalid_response_and_no_validation(mock_datarep):
    '''When VALIDATE_RESPONSE == False, confirm datarep ignores an
       invalid response.
    '''
    create_data = {'id': 42, 'value': 'foo'}
    invalid_response = {'id': 42, 'value': 'foo', 'extra_thing': 'foo'}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.post(svc_path, json=invalid_response)
        assert mock_datarep.create(create_data).data == invalid_response


def test_delete_with_invalid_response_and_no_validation(mock_datarep):
    '''When VALIDATE_RESPONSE == False, confirm datarep ignores an
       invalid response.
    '''
    return_data = {'status': 401}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.delete(svc_path, json=return_data)
        r = mock_datarep.delete()

        # Accessing data for an apparently deleted datarep should raise
        # a DataPullError.
        with pytest.raises(DataPullError):
            r.data


def test_delete_with_valid_response(mock_datarep, validate_response):
    '''When VALIDATE_RESPONSE == True, confirm successful deletion after
       receiving a valid response
    '''
    return_data = {'status': 204}
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.delete(svc_path, json=return_data)
        r = mock_datarep.delete()

        # Accessing data for a successfully deleted datarep should raise
        # a DataPullError
        with pytest.raises(DataPullError):
            r.data


def test_delete_with_invalid_response(mock_datarep, validate_response):
    '''When VALIDATE_RESPONSE == True, confirm that reschema raises a
       ValidationError on delete() if an invalid response is received
    '''
    return_data = {'status': 401}  # Unauthorized
    svc_path = 'http://hostname.nbttech.com/api/validate_me/1.0/anything/42'

    with requests_mock.mock() as m:
        m.delete(svc_path, json=return_data)

        with pytest.raises(reschema.exceptions.ValidationError):
            mock_datarep.delete()


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

    fragment = root['a'][2]
    assert fragment.jsonschema == root.jsonschema.by_pointer(ANY_FRAGMENT_PTR)
    assert fragment._data is datarep.DataRep.FRAGMENT
    assert fragment.data == resolve_pointer(root.data, ANY_FRAGMENT_PTR)
    assert fragment.root == root


def test_datarep_negative_getitem(mock_service):
    root = datarep.DataRep.from_schema(service=mock_service,
                                       uri=ANY_URI,
                                       jsonschema=ANY_DATA_SCHEMA,
                                       data=ANY_DATA)

    fragment = root['a'][-1]
    assert fragment.jsonschema == root.jsonschema.by_pointer(ANY_FRAGMENT_PTR)
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
        assert fragment.jsonschema == root.jsonschema.by_pointer(ptr)
        assert fragment._data == datarep.DataRep.FRAGMENT
        assert fragment.data == resolve_pointer(root.data, ptr)
        assert fragment.root == root


def test_datarep_getitem_negative_stepped_slice(mock_service):
    root = datarep.DataRep.from_schema(service=mock_service,
                                       uri=ANY_URI,
                                       jsonschema=ANY_DATA_SCHEMA,
                                       data=ANY_DATA)

    fragments = root['a'][-1:-4:-2]
    assert len(fragments) == 2
    for fragment, ptr in zip(fragments, ('/a/2', '/a/0')):
        assert fragment.jsonschema == root.jsonschema.by_pointer(ptr)
        assert fragment._data == datarep.DataRep.FRAGMENT
        assert fragment.data == resolve_pointer(root.data, ptr)
        assert fragment.root == root


def test_datarep_complex_structure(any_datarep_with_object_data):
    drod = any_datarep_with_object_data
    assert type(drod) is datarep.DictDataRep
    assert type(drod['b']) is datarep.ListDataRep
    assert type(drod['b'][0]) is datarep.DictDataRep


def test_datarep_additionalproperties(any_datarep_with_object_data):
    drod = any_datarep_with_object_data
    assert type(drod['b'][0]['c']) is datarep.ListDataRep
    assert type(drod['b'][0]['d']) is datarep.ListDataRep


def test_datarep_ref(ref_pair_datareps):
    from_ref = ref_pair_datareps.referencing['reference']
    assert type(from_ref) is datarep.DictDataRep
    assert type(from_ref['thing']) is datarep.ListDataRep
    assert type(from_ref['thing'][0]) is datarep.DataRep


def test_datarep_merge(merged_datarep):
    assert type(merged_datarep) is datarep.DictDataRep


@pytest.mark.xfail
def test_datarep_oneof(any_datarep_with_object_data):
    drod = any_datarep_with_object_data
    assert type(drod['b'][0]['c'][0]) is datarep.DictDataRep
    assert type(drod['b'][0]['c'][1]) is datarep.ListDataRep


def test_datarep_object___iter__(any_datarep_with_object_data):
    drod = any_datarep_with_object_data
    iterated_keys = []
    for key in drod:
        assert drod[key].data == drod.data[key]
        iterated_keys.append(key)
    data_keys = drod.data.keys()
    assert iterated_keys == data_keys


def test_datarep_object_iterkeys(any_datarep_with_object_data):
    drod = any_datarep_with_object_data
    # iterkeys() should just call plain __iter__() via the builtin.
    with mock.patch('__builtin__.iter', mock.MagicMock()) as patched:
        drod.iterkeys()
        patched.assert_called_once_with(drod)


def test_datarep_object_keys(any_datarep_with_object_data):
    drod = any_datarep_with_object_data
    assert drod.keys() == drod.data.keys()


def test_datarep_object_itervalues(any_datarep_with_object_data):
    drod = any_datarep_with_object_data
    data_values = drod.data.values()
    index = 0
    for value in drod.itervalues():
        assert value.data == data_values[index]
        index += 1

    assert index == len(data_values)


def test_datarep_object_values(any_datarep_with_object_data):
    drod = any_datarep_with_object_data
    assert [v.data for v in drod.values()] == drod.data.values()


def test_datarep_object_iteritems(any_datarep_with_object_data):
    drod = any_datarep_with_object_data
    data_items = drod.data.items()
    index = 0
    for items in drod.iteritems():
        assert (items[0], items[1].data) == data_items[index]
        index += 1

    assert index == len(data_items)


def test_datarep_object_items(any_datarep_with_object_data):
    drod = any_datarep_with_object_data
    assert [(kv[0], kv[1].data) for kv in drod.items()] == drod.data.items()


def test_datarep_array_index(any_datarep_fragment_with_array_data):
    drfad = any_datarep_fragment_with_array_data
    assert drfad.index(2) == drfad.data.index(2)


def test_datarep_array_index_not_found(any_datarep_fragment_with_array_data):
    drfad = any_datarep_fragment_with_array_data
    with pytest.raises(ValueError):
        drfad.index(100)


def test_datarep_array___iter__(any_datarep_fragment_with_array_data):
    drfad = any_datarep_fragment_with_array_data
    assert [x.data for x in iter(drfad)] == drfad.data


def test_exception():
    s = service.Service(ANY_SERVICE_DEF, ANY_URI)
    dr = datarep.DataRep.from_schema(s, uri=ANY_URI,
                                     jsonschema=ANY_DATA_SCHEMA)
    dr._getlink = True

    response = mock.Mock(requests.Response)
    response.status_code = 404
    response.text = ('{"error_id": 2, "error_text": "Ur doin it wrong",'
                     ' "error_info": {"details": false}}')
    response.headers = {'content-type': 'application/json'}
    r_json = json.loads(response.text)
    response.json = mock.Mock(return_value=r_json)

    def fake_request(*args, **kwargs):
        HTTPError.raise_by_status(response)

    with mock.patch('sleepwalker.service.Service.request',
                    side_effect=fake_request):
        with pytest.raises(HTTPNotFound) as einfo:
            dr.pull()
        exc_dr = einfo.value.datarep
        assert type(exc_dr) is datarep.DictDataRep
        assert exc_dr.data == r_json

        # Empty schemas appear as Multi schemas and that does not yet work.
        with pytest.raises(NotImplementedError):
            assert exc_dr['error_info']['details'].data is False

# ============ Execute method ==========================


@pytest.fixture
def datarep_with_link(mock_service):
    schema = reschema.jsonschema.Schema.parse(
        input={
            'type': 'object',
            'properties': {
                'foo': {'type': 'string'},
                'bar': {
                    'type': 'string',
                    'links': {'something': {
                        'method': 'GET',
                        'path': {
                            'template': '$/{foo}',
                            "vars": {"foo": "1/foo"},
                        },
                    }},
                },
            },
            'links': {'toplink': {
                'method': 'GET',
                'path': '$/{foo}',
            }},
        },
        name='any',
        servicedef=ANY_SERVICE_DEF)
    rep = datarep.DataRep.from_schema(mock_service, ANY_URI,
                                      jsonschema=schema)
    return rep


@pytest.fixture
def data_datarep_with_link(datarep_with_link):
    datarep_with_link.data = {"foo": "foo", "bar": "bar"}
    return datarep_with_link['bar']


def test_datarep_execute_with_data(data_datarep_with_link):
    rep = data_datarep_with_link
    with mock.patch.object(rep, "_request") as mock_request:
        rep.execute("something")
        mock_request.assert_called_once_with('GET', '/apis/foo/1.0/foo', None,
                                             None)


def test_datarep_execute_with_data_and_kwargs(data_datarep_with_link):
    rep = data_datarep_with_link
    with mock.patch.object(rep, "_request") as mock_request:
        rep.execute("something", foo="bar")
        mock_request.assert_called_once_with('GET', '/apis/foo/1.0/bar', None,
                                             None)


def test_datarep_execute(datarep_with_link):
    rep = datarep_with_link
    with mock.patch.object(rep, "_request") as mock_request:
        rep.execute("toplink", foo="foo")
        mock_request.assert_called_once_with('GET', '/apis/foo/1.0/foo', None,
                                             None)


def test_datarep_execute_raises(datarep_with_link):
    # A DataRep that has no get link cannot pull data to resolve other links,
    # so if no data is present and no kwargs are supplied, we must fallback on
    # raising an exception.
    rep = datarep_with_link
    with pytest.raises(reschema.exceptions.MissingParameter):
        rep.execute("toplink")
