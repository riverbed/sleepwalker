# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import unittest, re, logging, uritemplate
from reschema.jsonschema import Ref

from sleepwalker.service import Service
from sleepwalker.resource import Resource, Schema

class NoSchemaFound(Exception): pass

class Connection(object):

    def __init__(self, test):
        self.test = test
        self.restschemas = []

    def add_restschema(self, rs):
        self.restschemas.append(rs)
        
    def json_request(self, uri, method, data, params):
        print "%s %s params=%s, data=%s" % (method, uri, params, data)
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
                    values[v] = "(.*)"
                    
                uri_re = uritemplate.expand(template, values)
                if uri_re[0] == '$':
                    uri_re = "^" +  rs.servicePath + uri_re[1:] + "$"
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
        self.service.load_restschema("basic_schema.yml")
        self.service.conn = Connection(self)
        self.service.conn.add_restschema(self.service.restschema)
        
    def test_lookup(self):
        #resp = self.service.conn.json_request("/api/basic/1.0/x", "GET", None, None)
        #self.assertEqual(resp, 5)
        
        x = self.service.bind_resource('x')
        self.assertEqual(type(x), Resource)

        resp = x.get()
        self.assertEqual(resp.data, 5)
        
        resp = x.action(20)
        self.assertEqual(resp.data, 21)
        
        resp = x.action2()
        self.assertEqual(resp.data, {'t1':15, 't2': 'foo'})
        
if __name__ == '__main__':
    unittest.main()
    
