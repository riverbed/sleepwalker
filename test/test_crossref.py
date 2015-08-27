# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

import os
import logging
import unittest
import re
import urlparse

from sleepwalker.datarep import ListDataRep

from sim_server import \
    SimServer, UnknownUsername, BadPassword, MissingAuthHeader
from service_loader import \
    ServiceDefLoader, SERVICE_MANAGER, CONNECTION_MANAGER, \
    TEST_SERVER_MANAGER

logger = logging.getLogger(__name__)

TEST_PATH = os.path.abspath(os.path.dirname(__file__))

ServiceDefLoader.register_servicedef(
    'http://support.riverbed.com/apis/crossref.foo/1.0',
    os.path.join(TEST_PATH, "service_crossref_foo.yml"))

ServiceDefLoader.register_servicedef(
    'http://support.riverbed.com/apis/crossref.bar/1.0',
    os.path.join(TEST_PATH, "service_crossref_bar.yml"))


class CrossRefFooServer(SimServer):

    def __init__(self, *args, **kwargs):
        SimServer.__init__(self, *args, **kwargs)
        self.add_collection('foos', 'foo')

    def embed_bar_links_get(self, link, method, uri, data, params, headers):
        return {'name': 'embed_bar',
                'bar': {'id': 4,
                        'name': 'bar'}}


class CrossRefBarServer(SimServer):

    def bar_links_get(self, link, method, uri, data, params, headers):
        m = re.match(
            '^.*/api/(instance-([0-9]+)/)?crossref.bar/1.0/bars/([0-9]+)$',
            uri)
        if m.group(1):
            return "Bar-instance-%s-%s" % (m.group(2), m.group(3))
        else:
            return "Bar-%s" % m.group(3)


class FooBarTest(unittest.TestCase):

    def setUp(self):
        TEST_SERVER_MANAGER.reset()

        foo_id = 'http://support.riverbed.com/apis/crossref.foo/1.0'
        bar_id = 'http://support.riverbed.com/apis/crossref.bar/1.0'

        TEST_SERVER_MANAGER.register_server(
            'http://crossref-foo-server', foo_id, None,
            CrossRefFooServer, self)
        for i in range(3):
            TEST_SERVER_MANAGER.register_server(
                'http://crossref-bar-server-%d' % i, bar_id, None,
                CrossRefBarServer, self)
            for j in range(3):
                TEST_SERVER_MANAGER.register_server(
                    'http://crossref-bar-server-%d' % i, bar_id,
                    'instance-%d' % j, CrossRefBarServer, self)

    def test_foo(self):
        id = 'http://support.riverbed.com/apis/crossref.foo/1.0'
        self.foo_service = SERVICE_MANAGER.find_by_id(
            'http://crossref-foo-server', id)

        foos = self.foo_service.bind('foos')
        for i in range(2):
            foos.create(
                {'bar_id': i + 1,
                 'bar_server': 'http://crossref-bar-server-%d' % (i + 1),
                 'bar_instance': ''})
            for j in range(2):
                foos.create(
                    {'bar_id': i + 1,
                     'bar_server': 'http://crossref-bar-server-%d' % (i + 1),
                     'bar_instance': 'instance-%d' % (j + 1)})

        foos.pull()
        self.assertEqual(type(foos), ListDataRep)
        self.assertEqual(foos[0]['id'].data, 1)

        # There should be one and only one connection to the foo-server
        self.assertEqual(len(CONNECTION_MANAGER.conns), 1)
        self.assertTrue(('http://crossref-foo-server', None) in
                        CONNECTION_MANAGER.conns)

        bar = foos[0].follow('bar')
        self.assertEqual(bar.data, 'Bar-1')

        for foo in foos:
            bar_id = foo.data['bar_id']
            bar_instance = foo.data['bar_instance']

            bar = foo.follow('bar')
            self.assertEqual(bar.service.host,
                             'http://crossref-bar-server-%s' % bar_id)
            if bar_instance:
                self.assertEqual(bar.data, 'Bar-%s-%s' %
                                 (bar_instance, bar_id))
            else:
                self.assertEqual(bar.data, 'Bar-%s' % bar_id)

        # After following bar, each one should go do a new server,
        conns = CONNECTION_MANAGER.conns
        self.assertEqual(len(conns), 3)
        self.assertTrue(('http://crossref-foo-server', None) in conns)
        self.assertTrue(('http://crossref-bar-server-1', None) in conns)
        self.assertTrue(('http://crossref-bar-server-2', None) in conns)
        self.assertFalse(('http://crossref-bar-server-3', None) in conns)

    def test_embed_bar(self):
        id = 'http://support.riverbed.com/apis/crossref.foo/1.0'
        self.foo_service = SERVICE_MANAGER.find_by_id(
            'http://crossref-foo-server', id)

        embed_bar = self.foo_service.bind('embed_bar')
        print embed_bar


class FooBarAuthSameTest(unittest.TestCase):

    class Auth(object):
        def __init__(self, username, password):
            self.username = username
            self.password = password

        def __call__(self, req):
            req.headers['auth_header'] = (self.username, self.password)

        def __hash__(self):
            return hash((self.username, self.password))

        def __eq__(self, other):
            return (self.username == other.username and
                    self.password == other.password)

    def setUp(self):
        TEST_SERVER_MANAGER.reset()

        self.foo_host = 'http://crossref-foo-server'
        self.foo_id = 'http://support.riverbed.com/apis/crossref.foo/1.0'
        self.fooserver = TEST_SERVER_MANAGER.register_server(
            self.foo_host, self.foo_id, None, CrossRefFooServer, self)
        self.fooserver.allowed_auth = {'test1': 'password1',
                                       'test2': 'password2'}

        self.bar_host = 'http://crossref-bar-server'
        self.bar_id = 'http://support.riverbed.com/apis/crossref.bar/1.0'
        self.barserver = TEST_SERVER_MANAGER.register_server(
            self.bar_host, self.bar_id, None, CrossRefBarServer, self)
        self.barserver.allowed_auth = {'test1': 'password1'}

    def test_auth(self):
        # Find the foo service as user test1
        foo_service_1 = SERVICE_MANAGER.find_by_id(
            self.foo_host, self.foo_id,
            auth=FooBarAuthSameTest.Auth('test1', 'password1'))
        foos = foo_service_1.bind('foos')
        foos.create(
            {'bar_id': 1,
             'bar_server': 'http://crossref-bar-server',
             'bar_instance': ''})
        foos.pull()
        connmgr_conns = CONNECTION_MANAGER.conns
        # One connection to the foo server
        self.assertEqual(len(connmgr_conns), 1)

        # Follow a link to the bar service
        bar = foos[0].follow('bar')
        bar_service_1 = bar.service
        self.assertEqual(bar.data, 'Bar-1')
        self.assertEqual(bar_service_1.auth.username, 'test1')
        # Now a second connection -- to the bar server as test1
        self.assertEqual(len(connmgr_conns), 2)

        # Follow it again -- we should end up with a *different* service
        # object, but the same number of connections and same username
        bar = foos[0].follow('bar')
        bar_service_2 = bar.service
        self.assertEqual(bar.data, 'Bar-1')
        self.assertEqual(bar_service_2.auth.username, 'test1')
        self.assertEqual(len(connmgr_conns), 2)
        self.assertNotEqual(bar_service_1, bar_service_2)

        # Now establish switch to user 'test2'
        foo_service_1 = SERVICE_MANAGER.find_by_id(
            self.foo_host, self.foo_id,
            auth=FooBarAuthSameTest.Auth('test2', 'password2'))
        foos = foo_service_1.bind('foos')
        foos.create(
            {'bar_id': 1,
             'bar_server': 'http://crossref-bar-server',
             'bar_instance': ''})
        foos.pull()
        connmgr_conns = CONNECTION_MANAGER.conns
        # A third connection is established
        self.assertEqual(len(connmgr_conns), 3)

        # Try to follow a link to the bar service, this should fail
        # as the username 'test2' is not allowed on the bar server
        with self.assertRaises(UnknownUsername):
            bar = foos[0].follow('bar')
            # Note that simply following the link does not actually create
            # a connection, have to access data...
            bar.data

        # Will have a 4th connection, even though our auth is bad
        self.assertEqual(len(connmgr_conns), 4)


class FooBarAuthDiffTest(unittest.TestCase):

    class Auth(object):
        def __init__(self):
            self.auth = {}

        def add_auth(self, host, username, password):
            self.auth[host] = (username, password)

        def __call__(self, req):
            parsed = urlparse.urlparse(req.conn.host)
            if parsed.netloc in self.auth:
                req.headers['auth_header'] = self.auth[parsed.netloc]

    def setUp(self):
        TEST_SERVER_MANAGER.reset()

        self.foo_host = 'http://crossref-foo-server'
        self.foo_id = 'http://support.riverbed.com/apis/crossref.foo/1.0'
        self.fooserver = TEST_SERVER_MANAGER.register_server(
            self.foo_host, self.foo_id, None, CrossRefFooServer, self)
        self.fooserver.allowed_auth = {'test1': 'password1'}

        self.bar_host = 'http://crossref-bar-server'
        self.bar_id = 'http://support.riverbed.com/apis/crossref.bar/1.0'
        self.barserver = TEST_SERVER_MANAGER.register_server(
            self.bar_host, self.bar_id, None, CrossRefBarServer, self)
        self.barserver.allowed_auth = {'test1': 'password2'}

    def test_auth(self):
        auth = FooBarAuthDiffTest.Auth()
        auth.add_auth('crossref-foo-server', 'test1', 'password1')
        auth.add_auth('crossref-bar-server', 'test1', 'password2')

        # Find the foo service as user test1
        foo_service_1 = SERVICE_MANAGER.find_by_id(
            self.foo_host, self.foo_id, auth=auth)
        foos = foo_service_1.bind('foos')
        foos.create(
            {'bar_id': 1,
             'bar_server': 'http://crossref-bar-server',
             'bar_instance': ''})
        foos.pull()
        connmgr_conns = CONNECTION_MANAGER.conns
        # One connection to the foo server
        self.assertEqual(len(connmgr_conns), 1)

        # Follow a link to the bar service
        bar = foos[0].follow('bar')
        bar_service_1 = bar.service
        self.assertEqual(bar.data, 'Bar-1')
        self.assertEqual(bar_service_1.auth.auth['crossref-bar-server'][0],
                         'test1')
        # Now a second connection -- to the bar server as test1
        self.assertEqual(len(connmgr_conns), 2)

    def test_bad_auth(self):
        auth = FooBarAuthDiffTest.Auth()
        auth.add_auth('crossref-foo-server', 'test1', 'password1')

        # wrong password
        auth.add_auth('crossref-bar-server', 'test1', 'password3')

        # Find the foo service as user test1
        foo_service_1 = SERVICE_MANAGER.find_by_id(
            self.foo_host, self.foo_id, auth=auth)
        foos = foo_service_1.bind('foos')
        foos.create(
            {'bar_id': 1,
             'bar_server': 'http://crossref-bar-server',
             'bar_instance': ''})

        # Try to follow a link to the bar service
        with self.assertRaises(BadPassword):
            bar = foos[0].follow('bar')
            bar.data

    def test_missing_auth(self):
        auth = FooBarAuthDiffTest.Auth()
        auth.add_auth('crossref-foo-server', 'test1', 'password1')

        # Find the foo service as user test1
        foo_service_1 = SERVICE_MANAGER.find_by_id(
            self.foo_host, self.foo_id, auth=auth)
        foos = foo_service_1.bind('foos')
        foos.create(
            {'bar_id': 1,
             'bar_server': 'http://crossref-bar-server',
             'bar_instance': ''})

        # Try to follow a link to the bar service
        with self.assertRaises(MissingAuthHeader):
            bar = foos[0].follow('bar')
            bar.data


if __name__ == '__main__':
    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    unittest.main()
