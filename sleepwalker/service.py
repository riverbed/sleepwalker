# Copyright (c) 2013-2014 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/sleepwalker/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

"""
The `Service` class represents a single service supported by a server.
A `rest-schema` is bound to the service in order to take advantage
of the advanced features of `DataRep` instances to validate data,
execute links and follow relations.

Typical usage::

   >>> catalog_def = ServiceDef.create_from_file('catalog.yml')
   >>> catalog = Service(catalog_def)
   >>> catalog.add_connection('restserver.com')
   >>> book = catalog.bind('book', id=1)

"""


from .datarep import Schema
from .connection import Connection
from .exceptions import ServiceException, ResourceException, TypeException


class ConnectionHook(object):

    def connect(host):
        return NotImplementedError()


class ConnectionManager(object):

    def __init__(self):
        # Index of connections by host
        self.by_host = {}

        # List of connection hooks to use
        self._conn_hooks = []

    def add(self, host, conn):
        self.by_host[host] = conn

    def add_conn_hook(self, hook):
        self._conn_hooks.append(hook)

    def clear_hooks(self):
        self._conn_hooks = []

    def find(self, host):
        if host not in self.by_host:
            conn = None
            for hook in self._conn_hooks:
                conn = hook.connect(host)
                if conn:
                    break
            if conn is None:
                raise ConnectionError(
                    'Failed to establish a connection to %s' % host)
            self.add(host, conn)
        else:
            conn = self.by_host[host]
        return conn


class ServiceManager(object):

    def __init__(self, servicedef_manager, connection_manager):

        self.servicedef_manager = servicedef_manager
        self.connection_manager = connection_manager

        # Indexed by tuple <id, instance>
        self.by_id = {}

        # Indexed by tuple <name, version, provider, instance>
        self.by_name = {}

    def add(self, service):
        """ Add a Service instance to the manager cache. """

        self.by_id[(service.host, service.servicedef.id,
                    service.instance)] = service
        self.by_name[(service.host, service.servicedef.name,
                      service.servicedef.version, service.servicedef.provider,
                      service.instance)] = service


    def find_by_id(self, host, id, instance=None):
        """ Find a Service object by service id.

        :param host: IP address or hostname
        :param id: fully qualified id of the service definition
        :param instance: unique instance identifier for this
            service relative to the same host (by connection)

        """
        id_key = (host, id, instance)
        if id_key not in self.by_id:
            servicedef = self.servicedef_manager.find_by_id(id)
            conn = self.connection_manager.find(host)
            service = Service(servicedef, host=host, instance=instance,
                              connection=conn, manager=self)
            self.add(service)
        else:
            service = self.by_id[id_key]
        return service

    def find_by_name(self, host, name, version,
                     provider='riverbed', instance=None):
        """ Find a Service object by service <name,version,provider>

        :param manager: used to lookup/load the service definition
        :param name: the service name
        :param version: the service version
        :param provider: the provider of the service
        :param instance: unique instance identifier for this
            service relative to the same host (by connection)

        """
        name_key = (host, name, version, provider, instance)
        if name_key not in self.by_name:
            servicedef = (self.servicedef_manager
                          .find_by_name(name, version, provider))
            conn = self.connection_manager.find(host)
            service = Service(servicedef, host=host, instance=instance,
                              connection=conn, manager=self)
            self.add(service)
        else:
            service = self.by_name[name_key]

        return service


class Service(object):

    # Default api root for servicepath when not provided
    # by the user
    DEFAULT_ROOT = '/api'

    def __init__(self, servicedef, host, instance=None,
                 servicepath=None, connection=None, manager=None):
        """ Create a Service object

        :param servicedef: related ServiceDef for this Service

        :param host: IP address or hostname

        :param instance: unique instance identifier for this
            service relative to the same host (by connection)

        :param servicepath: URI prefix excluding host/port
            for all resources for this service.  Defaults
            to /api/<instance>/<name>/<version>.

        :param connection: connection to the target server
            to use for all API calls

        """
        self.servicedef = servicedef
        self.host = host
        self.instance = instance
        if servicepath is None:
            # Default service path is built by joining
            # root, instance (if not null), name and version
            paths = [p for p in [Service.DEFAULT_ROOT,
                                 instance,
                                 servicedef.name,
                                 servicedef.version] if p is not None]

            servicepath = host + '/'.join(paths)

        self.servicepath = servicepath
        self.connection = connection
        self.headers = {}

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
