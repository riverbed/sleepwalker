# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import re
import logging
import uritemplate
import string
import copy

logger = logging.getLogger(__name__)


class SimConnection(object):
    """ Connection test class which implements a CRUD server. """

    def __init__(self, test=None):
        self.test = test
        self.restschemas = []

        self._next_id = {}
        self._collections = {}
        self._members = []
        
    def add_collection(self, name, member):
        self._next_id[name] = 1
        self._collections[name] = {}
        self._members.append(member)
        
    def add_restschema(self, rs):
        self.restschemas.append(rs)

    def json_request(self, method, uri, data, params, headers):
        logger.info("%s %s params=%s, data=%s" % (method, uri, params, data))
        for rs in self.restschemas:
            m = re.match("^%s(.*)$" % rs.servicePath, uri)
            if m:
                break

        self.test and self.test.assertIsNotNone(m)

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

                logger.debug("matched link: %s (%s) (req %s, resp %s)" %
                             (link, link.name, link.request, link.response))

                if link.request is not None:
                    link.request.validate(data)

                n = link.fullname()
                n = ''.join([c if c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ01234567890"
                             else '_' for c in n])
                logger.debug("looking for func %s" % n)
                
                if hasattr(self, n):
                    func = self.__getattribute__(n)
                    logger.debug("calling func %s" % n)
                    return func(link, method, uri, data, params, headers)
                elif (  link.schema.name in self._collections.keys() and
                        hasattr(self, 'collection_' + link.name)):
                    n = 'collection_' + link.name
                    func = self.__getattribute__(n)
                    logger.debug("calling func %s" % n)
                    return func(link, method, uri, data, params, headers)
                elif (  link.schema.name in self._members and
                        hasattr(self, 'member_' + link.name)):
                    n = 'member_' + link.name
                    func = self.__getattribute__(n)
                    logger.debug("calling func %s" % n)
                    return func(link, method, uri, data, params, headers)
                else:
                    raise KeyError("No handler defined for link: %s => %s" % (link.name, n))

    def member_get(self, link, method, uri, data, params, headers):
        logger.debug("Processing get: %s" % uri)
        m = re.match('.*/([a-z]*)/([0-9]+)', uri)
        collection = m.group(1)
        id_ = int(m.group(2))
        self.test and self.test.assertEqual(id_ in self._collections[collection], True)
        return copy.deepcopy(self._collections[collection][id_])

    def member_set(self, link, method, uri, data, params, headers):
        logger.debug("Processing set: %s => %s" % (uri, data))
        m = re.match('.*/([a-z]*)/([0-9]+)', uri)
        collection = m.group(1)
        id_ = int(m.group(2))
        newdata = copy.deepcopy(data)
        newdata['id'] = id_
        self.test and self.test.assertEqual(id_ in self._collections[collection], True)
        self._collections[collection][id_] = newdata
        return copy.deepcopy(newdata)

    def member_delete(self, link, method, uri, data, params, headers):
        logger.debug("Processing delete: %s => %s" % (uri, data))
        m = re.match('.*/([a-z]*)/([0-9]+)', uri)
        collection = m.group(1)
        id_ = int(m.group(2))
        self.test and self.test.assertEqual(id_ in self._collections[collection], True)
        del self._collections[collection][id_]
        
    def collection_get(self, link, method, uri, data, params, headers):
        logger.debug("Processing get: %s => %s %s" % (uri, data, params))
        m = re.match('.*/([a-z]*)', uri)
        collection = m.group(1)
        return self._collections[collection].keys()

    def collection_create(self, link, method, uri, data, params, headers):
        logger.debug("Processing create: %s => %s" % (uri, data))
        m = re.match('.*/([a-z]*)', uri)
        collection = m.group(1)
        id_ = self._next_id[collection]
        self._next_id[collection] = self._next_id[collection] + 1
        logger.debug("Saving new items[%s] => %s" % (id_, data))
        newdata = copy.deepcopy(data)
        newdata['id'] = id_
        self.test and self.test.assertEqual(id_ not in self._collections[collection], True)
        self._collections[collection][id_] = newdata
        return copy.deepcopy(newdata)
