# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

from reschema import RestSchema

from sleepwalker.resource import Resource, Schema
from sleepwalker.connection import Connection

class ServiceException(Exception): pass


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
        if self.restschema is None:
            raise ServiceException("No rest-schema")

        jsonschema = self.restschema.find_resource(name)
        schema = Schema(self, jsonschema)
        return schema.bind(**kwargs)

    def lookup_resource(self, name):
        if self.restschema is None:
            raise ServiceException("No rest-schema")
        jsonschema = self.restschema.find_resource(name)
        schema = Schema(self, jsonschema)
        return schema

    def lookup_type(self, name):
        if self.restschema is None:
            raise ServiceException("No rest-schema")
        jsonschema = self.restschema.find_type(name)
        schema = Schema(self, jsonschema)
        return schema
