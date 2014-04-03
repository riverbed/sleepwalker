# Copyright (c) 2013-2014 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/sleepwalker/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import os
import logging
import unittest
import re

from sleepwalker.datarep import ListDataRep

from sim_server import SimServer
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

        TEST_SERVER_MANAGER.register_server('http://crossref-foo-server',
                                            CrossRefFooServer, self)
        TEST_SERVER_MANAGER.register_server('http://crossref-bar-server-1',
                                            CrossRefBarServer, self)
        TEST_SERVER_MANAGER.register_server('http://crossref-bar-server-2',
                                            CrossRefBarServer, self)
        TEST_SERVER_MANAGER.register_server('http://crossref-bar-server-3',
                                            CrossRefBarServer, self)

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
        self.assertEqual(len(CONNECTION_MANAGER.by_host), 1)
        self.assertTrue('http://crossref-foo-server' in
                        CONNECTION_MANAGER.by_host)

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
        connmgr_by_host = CONNECTION_MANAGER.by_host
        self.assertEqual(len(connmgr_by_host), 3)
        self.assertTrue('http://crossref-foo-server' in connmgr_by_host)
        self.assertTrue('http://crossref-bar-server-1' in connmgr_by_host)
        self.assertTrue('http://crossref-bar-server-2' in connmgr_by_host)
        self.assertFalse('http://crossref-bar-server-3' in connmgr_by_host)


if __name__ == '__main__':
    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    unittest.main()
