# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

from reschema import RestSchema

from .datarep import Schema
from .connection import Connection
from .exceptions import ServiceException, ResourceException, TypeException


class Service(object):

    def __init__(self):
        self.restschema = None
        self.connection = None
        
    def add_connection(self, hostname, auth=None, port=None, verify=True):
        """ Initialize new connection to hostname

            If an existing connection would rather be used, simply
            assign it to the `connection` instance variable instead.
        """
        # just a passthrough to Connection init, do we need this?
        self.connection = Connection(hostname, auth, port, verify)

    def request(self, method, uri, body=None, params=None, headers=None):
        """ Make request through connection and return result. """
        if not self.connection:
            raise ServiceException('No connection defined for service.')
        return self.connection.json_request(method, uri, body, params, headers)

    @property
    def response(self):
        """ Last response from server. """
        try:
            return self.connection.response
        except:
            return None

    def fetch_restschema(self):
        """ Fetch the hosted rest-schema. """
        # TODO compare local version if any to hosted version
        # how to perform version checks, and what is the schema uri?
        pass

    def load_restschema(self, filename):
        """ Load rest-schema from the given filename. """

        self.restschema = RestSchema()
        self.restschema.load(filename)

    def bind(self, _resource_name, **kwargs):
        """ Look up resource `_resource_name`, bind it and return a DataRep.

            `_resource_name` - name of resource
            `**kwargs` - dict of attributes required to bind resource
        """
        if self.restschema is None:
            raise ServiceException("No rest-schema")

        jsonschema = self.restschema.find_resource(_resource_name)
        schema = Schema(self, jsonschema)
        return schema.bind(**kwargs)

    def _lookup(self, name, lookup, exception_class):
        if self.restschema is None:
            raise ServiceException("No rest-schema defined")

        try:
            jsonschema = lookup(name)
        except KeyError:
            raise exception_class('%s not found in schema' % name)

        schema = Schema(self, jsonschema)
        return schema

    def lookup_resource(self, name):
        """ Look up `name` as a resource, and return a Schema

            `name` - name of resource
        """
        return self._lookup(name, self.restschema.find_resource, ResourceException)

    def lookup_type(self, name):
        """ Look up type `name`, and return a Schema

            `name` - name of type
        """
        return self._lookup(name, self.restschema.find_type, TypeException)
