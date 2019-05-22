# Copyright (c) 2019 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

import re
import logging
import uritemplate
import urllib.parse
import string
import copy

from reschema.util import uritemplate_required_variables


logger = logging.getLogger(__name__)


class MissingAuthHeader(Exception):
    pass


class UnknownUsername(Exception):
    pass


class BadPassword(Exception):
    pass


class SimServer(object):
    """ Server test class which implements a CRUD server. """

    def __init__(self, service, test=None, allowed_auth=None):
        self.test = test
        self.service = service
        self._next_id = {}
        self._collections = {}
        self._members = []
        self.allowed_auth = allowed_auth

    def close(self):
        pass

    def add_collection(self, name, member):
        self._next_id[name] = 1
        self._collections[name] = {}
        self._members.append(member)

    def request(self, req):
        if self.allowed_auth:
            if 'auth_header' not in req.headers:
                raise MissingAuthHeader()
            username, password = req.headers.get('auth_header')

            if username not in self.allowed_auth:
                raise UnknownUsername()

            if password != self.allowed_auth[username]:
                raise BadPassword()

        method = req.method
        uri = req.uri
        data = req.data
        params = req.params
        headers = req.headers

        service = self.service

        r = urllib.parse.urlparse(uri)
        if r.query:
            params = params or {}
            for k, v in dict(urllib.parse.parse_qsl(r.query)).items():
                params[k] = v
            parts = list(r)
            parts[4] = ''
            parts[5] = ''
            uri = urllib.parse.urlunparse(parts)

        logger.info("%s %s params=%s, data=%s" % (method, uri, params, data))

        for r in service.servicedef.resources.values():
            for link in r.links.values():
                if ((link.method is None) or (method != link.method) or
                        (link.path is None)):
                    continue
                template = link.path.template
                vars = uritemplate_required_variables(template)
                values = {}
                for v in vars:
                    values[v] = "__VAR__"

                uri_re = uritemplate.expand(template, values)
                if uri_re[0] == '$':
                    uri_re = "^" + service.servicepath + uri_re[1:] + "$"
                uri_re = str.replace(uri_re, "__VAR__", "([^/]+)")
                logger.debug("matching %s against %s" % (uri, uri_re))
                m = re.match(uri_re, uri)
                if not m:
                    continue

                logger.debug("matched link: %s (%s) (req %s, resp %s)" %
                             (link, link.name, link.request, link.response))

                if link.request is not None:
                    link.request.validate(data)

                n = link.fullname()
                n = ''.join([c if c in ("abcdefghijklmnopqrstuvwxyz"
                                        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                        "01234567890")
                             else '_' for c in n])
                logger.debug("looking for func %s" % n)

                if hasattr(self, n):
                    func = self.__getattribute__(n)
                    logger.debug("calling func %s" % n)
                    return func(link, method, uri, data, params, headers)
                elif (link.schema.name in self._collections.keys() and
                      hasattr(self, 'collection_' + link.name)):
                    n = 'collection_' + link.name
                    func = self.__getattribute__(n)
                    logger.debug("calling func %s" % n)
                    return func(link, method, uri, data, params, headers)
                elif (link.schema.name in self._members and
                      hasattr(self, 'member_' + link.name)):
                    n = 'member_' + link.name
                    func = self.__getattribute__(n)
                    logger.debug("calling func %s" % n)
                    return func(link, method, uri, data, params, headers)
                else:
                    raise KeyError("No handler defined for link: %s => %s" %
                                   (link.name, n))

    def member_get(self, link, method, uri, data, params, headers):
        logger.debug("Processing get: %s" % uri)
        m = re.match('.*/([a-z]*)/([0-9]+)', uri)
        collection = m.group(1)
        id_ = int(m.group(2))
        in_collection = (id_ in self._collections[collection])
        self.test and self.test.assertEqual(in_collection, True)
        return copy.deepcopy(self._collections[collection][id_])

    def member_set(self, link, method, uri, data, params, headers):
        logger.debug("Processing set: %s => %s" % (uri, data))
        m = re.match('.*/([a-z]*)/([0-9]+)', uri)
        collection = m.group(1)
        id_ = int(m.group(2))
        newdata = copy.deepcopy(data)
        newdata['id'] = id_
        in_collection = id_ in self._collections[collection]
        self.test and self.test.assertEqual(in_collection, True)
        self._collections[collection][id_] = newdata
        return copy.deepcopy(newdata)

    def member_delete(self, link, method, uri, data, params, headers):
        logger.debug("Processing delete: %s => %s" % (uri, data))
        m = re.match('.*/([a-z]*)/([0-9]+)', uri)
        collection = m.group(1)
        id_ = int(m.group(2))
        in_collection = id_ in self._collections[collection]
        self.test and self.test.assertEqual(in_collection, True)
        del self._collections[collection][id_]

    def collection_get(self, link, method, uri, data, params, headers):
        logger.debug("Processing get: %s => %s %s" % (uri, data, params))
        m = re.match('.*/([a-z]*)', uri)
        collection_name = m.group(1)
        collection = self._collections[collection_name]
        keys = list(collection.keys())
        keys.sort()
        return [collection[k] for k in keys]

    def collection_create(self, link, method, uri, data, params, headers):
        logger.debug("Processing create: %s => %s" % (uri, data))
        m = re.match('.*/([a-z]*)', uri)
        collection = m.group(1)
        id_ = self._next_id[collection]
        self._next_id[collection] = self._next_id[collection] + 1
        logger.debug("Saving new items[%s] => %s" % (id_, data))
        newdata = copy.deepcopy(data)
        newdata['id'] = id_
        not_in_collection = id_ not in self._collections[collection]
        self.test and self.test.assertEqual(not_in_collection, True)
        self._collections[collection][id_] = newdata
        return copy.deepcopy(newdata)
