# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import os
import re
import string
import logging
import unittest
import urlparse

import uritemplate
from reschema.jsonschema import Ref
from requests.exceptions import HTTPError

from sleepwalker.service import Service
from sleepwalker.resource import Resource
from sleepwalker.connection import Connection, URLError

logger = logging.getLogger(__name__)

TEST_PATH = os.path.abspath(os.path.dirname(__file__))


class TestConnection(object):
    """ Connection test class which echos 'example's back from a restschema.
    """

    def __init__(self, test):
        self.test = test
        self.restschemas = []

    def add_restschema(self, rs):
        self.restschemas.append(rs)
        
    def json_request(self, method, uri, data, params, headers):
        logger.info("%s %s params=%s, data=%s" % (method, uri, params, data))
        for rs in self.restschemas:
            m = re.match("^%s(.*)$" % rs.servicePath, uri)
            if m:
                break

        self.test.assertIsNotNone(m)

        for r in rs.resources.values():
            for link in r.links.values():
                if ((link.method is None) or (method != link.method) or
                    (link.path is None)):
                    continue
                template = link.path.template
                vars = uritemplate.variables(template)
                values = {}
                for v in vars:
                    values[v] = "__VAR__"
                    
                uri_re = uritemplate.expand(template, values)
                if uri_re[0] == '$':
                    uri_re = "^" + rs.servicePath + uri_re[1:] + "$"
                uri_re = string.replace(uri_re, "__VAR__", "(.*)")
                logger.debug("matching %s against %s" % (uri, uri_re))
                m = re.match(uri_re, uri)
                if not m:
                    continue

                if link.request is not None:
                    r = link.request
                    if type(r) is Ref:
                        r = r.refschema
                    r.validate(data)
                    self.test.assertEqual(data, r.example)

                if link.response is not None:
                    if type(link.response) is Ref:
                        return link.response.refschema.example
                    return link.response.example


class BasicTest(unittest.TestCase):

    def setUp(self):
        self.service = Service()
        self.service.load_restschema(os.path.join(TEST_PATH, "basic_schema.yml"))
        self.service.connection = TestConnection(self)
        self.service.connection.add_restschema(self.service.restschema)

    def test_x(self):
        x = self.service.bind_resource('x')
        self.assertEqual(type(x), Resource)
        self.assertEqual(x.data, None)

        resp = x.links.get()
        self.assertEqual(resp, x)
        self.assertEqual(x.data, 5)

        resp = x.links.action(20)
        self.assertEqual(resp.data, 21)
        
        resp = x.links.action2()
        self.assertEqual(resp.data, {'t1': 15, 't2': 'foo'})

        x.data = 0
        val = x.get()
        self.assertEqual(val, 5)

    def test_item(self):
        item_schema = self.service.lookup_resource('item')
        item = item_schema.bind(id=1)

        resp = item.links.get()
        self.assertEqual(item, resp)
        logger.debug(item.data)
        self.assertEqual(item.data, {'id': 1, 'label': 'foo'})


HTTPBIN = os.environ.get('HTTPBIN_URL', 'http://httpbin.org/').rstrip('/') + '/'
HTTPSBIN = os.environ.get('HTTPSBIN_URL', 'https://httpbin.org/').rstrip('/') + '/'


def httpbin(*suffix):
    """Returns url for HTTPBIN resource."""
    return urlparse.urljoin(HTTPBIN, '/'.join(suffix))


class ConnectionTest(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_hostnames(self):
        conn = Connection(HTTPBIN)
        self.assertEqual(conn.hostname, HTTPBIN)

        conn = Connection(HTTPSBIN)
        self.assertEqual(conn.hostname, HTTPSBIN)

        conn = Connection('example.com', port='80')
        self.assertEqual(conn.hostname, 'http://example.com')

        conn = Connection('example.com', port='443')
        self.assertEqual(conn.hostname, 'https://example.com')

        conn = Connection('example.com', port='20483')
        self.assertEqual(conn.hostname, 'https://example.com:20483')

    def test_port_mismatch(self):
        with self.assertRaises(URLError):
            Connection('example.com:20483', port=666)

    def test_json_request(self):
        conn = Connection(HTTPBIN)
        r = conn.json_request('GET', httpbin('get'))
        self.assertEqual(r['headers']['Accept'], 'application/json')
        self.assertEqual(r['headers']['Content-Type'], 'application/json')
        self.assertEqual(conn.response.status_code, 200)

    def test_404(self):
        conn = Connection(HTTPBIN)
        with self.assertRaises(HTTPError):
            conn.json_request('GET', httpbin('get/notfound'))


if __name__ == '__main__':
    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    unittest.main()
