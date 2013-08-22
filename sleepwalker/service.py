# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

from reschema import RestSchema

from .resource import Resource, Schema
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

    def fetch_restschema(self):
        """Fetch the hosted rest-schema."""
        # TODO compare local version if any to hosted version
        # how to perform version checks, and what is the schema uri?
        pass

    def load_restschema(self, filename):
        """Load rest-schema from the given filename."""

        self.restschema = RestSchema()
        self.restschema.load(filename)

    def bind_resource(self, name, **kwargs):
        """ Look up resource `name`, bind it and return the bound Resource.

            `name` - name of resource
            `**kwargs` - dict of attributes required to bind resource
        """
        if self.restschema is None:
            raise ServiceException("No rest-schema")

        jsonschema = self.restschema.find_resource(name)
        schema = Schema(self, jsonschema)
        return schema.bind(**kwargs)

    def lookup_resource(self, name):
        """ Look up resource `name`, and return the schema

            `name` - name of resource
        """
        if self.restschema is None:
            raise ServiceException("No rest-schema")
        try:
            jsonschema = self.restschema.find_resource(name)
            schema = Schema(self, jsonschema)
            return schema
        except KeyError:
            raise ResourceException('Resource %s not found in schema' % name)

    def lookup_type(self, name):
        """ Look up type `name`, and return the schema

            `name` - name of type
        """
        if self.restschema is None:
            raise ServiceException("No rest-schema")
        try:
            jsonschema = self.restschema.find_type(name)
            schema = Schema(self, jsonschema)
            return schema
        except KeyError:
            raise TypeException('Type %s not found in schema' % name)
