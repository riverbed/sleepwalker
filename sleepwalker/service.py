# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

"""
The `Service` class represents a single service supported by a server.
A `rest-schema` is bound to the service in order to take advantage
of the advanced features of `DataRep` instances to validate data,
execute links and follow relations.

Typical usage::

   >>> catalog = Service()
   >>> catalog.add_connection('restserver.com')
   >>> catalog.load_servicedef('examples/catalog.yml')
   >>> book = catalog.bind('book', id=1)

"""


from reschema import ServiceDef

from .datarep import Schema
from .connection import Connection
from .exceptions import ServiceException, ResourceException, TypeException


class Service(object):

    def __init__(self):
        self.servicedef = None
        self.connection = None
        self.headers = {}
        
    def add_connection(self, hostname, auth=None, port=None, verify=True):
        """ Initialize new connection to hostname

            If an existing connection would rather be used, simply
            assign it to the `connection` instance variable instead.
        """
        # just a passthrough to Connection init, do we need this?
        self.connection = Connection(hostname, auth, port, verify)

    def add_headers(self, headers):
        self.headers.update(headers)

    def request(self, method, uri, body=None, params=None, headers=None):
        """ Make request through connection and return result. """
        if not self.connection:
            raise ServiceException('No connection defined for service.')

        if headers is None:
            # No passed headers, but service has defined headers, use them
            headers = self.headers
        elif self.headers is not None:
            # Passed headeers and service headers, merge
            headers = copy.copy(headers)
            headers.update(self.headers)

        return self.connection.json_request(method, uri, body, params, headers)
    
    @property
    def response(self):
        """ Last response from server. """
        if self.connection is None or self.connection.response is None:
            return None
        return self.connection.response

    def fetch_servicedef(self):
        """ Fetch the hosted rest-schema. """
        # TODO compare local version if any to hosted version
        # how to perform version checks, and what is the schema uri?
        pass

    def load_servicedef(self, filename):
        """ Load rest-schema from the given filename. """

        self.servicedef = ServiceDef()
        self.servicedef.load(filename)

    def bind(self, _resource_name, **kwargs):
        """ Look up resource `_resource_name`, bind it and return a DataRep.

            `_resource_name` - name of resource
            `**kwargs` - dict of attributes required to bind resource
        """
        if self.servicedef is None:
            raise ServiceException("No rest-schema")

        jsonschema = self.servicedef.find_resource(_resource_name)
        schema = Schema(self, jsonschema)
        return schema.bind(**kwargs)

    def _lookup(self, name, lookup, exception_class):
        if self.servicedef is None:
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
        return self._lookup(name, self.servicedef.find_resource,
                            ResourceException)

    def lookup_type(self, name):
        """ Look up type `name`, and return a Schema

            `name` - name of type
        """
        return self._lookup(name, self.servicedef.find_type, TypeException)
