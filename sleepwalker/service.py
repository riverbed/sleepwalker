# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

"""
The `Service` class represents a single service instance supported by
a server.  Each service is associated with an instance of a service
defintion (`ServiceDef`), which is the complete map of resources and
operations that are supported by this service.

A separate `Service` object is required for each unique <`service id`,
`host`, `instance`> triplet.  In addition to the `service id` which
identifies the service, `host` identifies the particular server that
is hosting the service, and `instance` is an optional qualifier in the
event that the server is offering multiple instances of the same
service defintion at different URI prefixes.

Although a `Service` instance can be created directly, the `ServiceManager`
is normally used to instantiate services as needed.  This is particularly
important when following links and relations that lead to another Service
instance.  Following such references will leverage ServiceManager to
look for an already instantiated Service that matches, otherwise it
will create a new Service instance.

The `Service.bind()` method is used to instantiate a `DataRep` for a
named resource, which is then used to access and modify resources on
the server.  Any interaction with the server is via a `Connection`.

Manual Service creation
-----------------------

Creating a `Service` object requires a `ServiceDef` and a `Connection`
instance:

.. code-block:: python

   # Load the bookstore service definition from a file
   >>> bookstore_def = ServiceDef.create_from_file('bookstore.yml')

   # Establish a connection to the bookstore server
   >>> conn = Connection('http://bookstore-server.com:8080')

   # Create the Service object
   >>> bookstore = Service(bookstore_def, 'http://bookstore-server.com:8080',
                         connection=conn)

   # Bind a DataRep to a 'book' instance and retrieve data for this
   # book from the server
   >>> book = bookstore.bind('book', id=1)
   >>> book.data
   { 'id': 1, 'title': 'A book' }

The `bookstore` instance can be used to access any and all resources
associated directly with this service.  Any attempt to follow
references to or leverage types in another service will not be
possible.

Using Managers
--------------

For larger projects that span multiple services and hosts, it is easier
to use the various managers:

* `ServiceDefManager` - loads and creates `ServiceDef` instances only
  as needed; creates only a single instance per unique service `id`.

* `ConnectionManager` - manages connections to hosts; establishes a
  single connection to each unique host that may be hosting multiple
  services.

* `ServiceManager` - manages services; creates a unique `Service` for
  each unique <`service id`, `host`, `instance`> triplet.

Typically only a single manager of each type will be created:

.. code-block:: python

   # Create a ServiceDefManager to manage service definitions The
   # CustomServiceDefLoader implements the ServiceDefLoadHook andmust
   # be defined in order to load service definitions on this system.
   >>> svcdef_mgr = ServiceDefManager()
   >>> svcdef_mgr.add_load_hook(CustomServiceDefLoader)

   # Create a ConnectionManager to automatically establish connections
   # as needed to hosts.  The CustomConnector implements
   # ConnectionHook and must be defined to create a Connection object
   # to the target host as needed.
   >>> conn_mgr = ConnectionManager()
   >>> conn_mgr.add_conn_hook(CustomConnecter)

   # Create a ServiceManager that will use the above to establish
   # connections
   >>> svc_mgr = ServiceManager(servicedef_manager=svcdef_mgr,
                                connection_manager=conn_mgr)

The ServiceManager then becomes the primary entry point for loading
services:

.. code-block:: python

   # Ask the ServiceManager for the bookstore Service object
   >>> bookstore = svc_mgr.find_by_name(host='http://bookstore-server.com:8080',
                                      name='bookstore', version='1.0')

   # Bind a DataRep to a 'book' instance and retrieve data for this
   # book from the server
   >>> book = bookstore.bind('book', id=1)
   >>> book.data
   { 'id': 1, 'title': 'A book' }

Any subsequent calls to `svc_mgr` for the `bookstore/1.0` service on this
particular host will return the same `Service` instance.

Authentication
==============

Authentication in general is opaque to `Service` instances.  If access
to the service's host requires authentication, the `auth` parameter is
passed at creation.  The `auth` parameter is stored and passed on to
the `Connection` or `ConnectionManager` when a request is made.  As
such, `auth` is not processed or interpreted at all by the service
object.

When used in conjunction with the managers, the `auth` object must
be capable of supporting authentication for the same context across
different hosts.  For example, for the authentication context of the
user 'Christopher J. White`, an auth object is built that knows
the username and password on `server-1` as `cwhite`/`getmein`, but on
`server-2` it is `chriswhite`/`abc123`.  The auth object as a
callable can inspect a request generated by the underlying connection
class to determine what the target host and service is, and pick
the appropriate credentials.

Connection
----------

A single connection object may be used by multiple services.  However,
each connection is associated with a single authentication session.
As such, one connection must be establshied to the same host for each
unique user (or access code or whatever constitutes a unique auth
session).

The default `Connection` class is layered on top of requests sessions,
and requests is designed to support a single auth handler for the
session.  As such, instantiating a Connection will take an 'auth'
callable:

.. code-block:: python

  >>> conn = Connection(host, auth)

Note that while a single requests session can only handle a single auth
context, it's conceivable that the underlying socket could support
multiplexing multiple different auth contexts.  Someone would have to
play with this.

ConnectionManager
-----------------

In order to share the same connection for a <host,auth> pair,
ConnectionManager must also be authentication aware.  The `find()`
method takes both a host and an associated auth.

.. code-block:: python

  >>> cm = ConnectionManager()
  >>> conn = cm.find(host, auth)

Like `Service` and `ServiceManager`, the auth parameter is not
processed by ConnectionManager, merely passed along.  This implies the
ConnectionHook.connect() must also take auth:

.. code-block:: python

  class ConnectionHook(object);
      def connect(host, auth)

`ConnectionManager` caches connections based on the tuple <host,
auth>.  In the event that `auth` is a callable (which is typical and
in the style of Python `requests`), the hashing will be based on the
callable __hash__() and __eq__() methods.  If not explicitly defined,
they will be based on the default implementations which are
essentially based on memory instances.

Service
-------

Each service object is bound to a connection.  This is either manual
(instantiation with a connection argument), or via a
ConnectionManager.  It is the latter case that is more interesting
because it enables bouncing from service to service, potentially to
another host.  As such, Service takes an 'auth' parameter directly:

.. code-block:: python

   >>> s = Service(<servicedef>, <host>, connectionmanager=cm, auth=<auth>)

When needed (ie, when the client tries to issue a request via the
service), the Service class will call to connection manager to find a
connection to the desired host using the given auth context.

Note that without a ServiceManager, it is still not actually possible to
jump from one service to another seamlessly.

ServiceManager
--------------

ServiceManager pulls it all together adding the `auth` paramter
to the `find_by_name()` and `find_by_id()` methods.

.. code-block:: python

   >>> sm = ServiceManager(connectionmanager=cm, servicedef_manager=sdm)
   >>> s = sm.find_by_name(<host>, <name>, <version>, auth=<auth>)

The Service object returned is equivalent to the following manual
instantiation:

.. code-block:: python

   >>> s = Service(<servicedef>, <host>, servicemanager=sm, auth=auth)

When following a link/relation that results in a different service and
possibly different host, the `auth` object is passed along.  This is
the reason that the `auth` object must be smart enough to handle
authentication for multiple hosts.

"""

import copy
import logging

from sleepwalker.datarep import Schema
from sleepwalker.exceptions import \
    ServiceException, ResourceException, TypeException

logger = logging.getLogger(__name__)


class ServiceManager(object):
    """ A ServiceManager instance manages multiple Services instances.

    A single `ServiceManager` instance creates `Service` instances as
    needed, caching instances as they are created.  A unique `Service`
    is identified by the tuple <`service id`, `host`, `instance`>

    The `auth` parameter accepted by `find_by_id()` and `find_by_name()`
    is an object representing authentication credentials.  This object
    is passed on to `ConnectionManager` which in turn passes it
    on to the appropriate `ConnectionHook` when establishing new
    connections.  In order to facilitate seamless transistions from
    one service to another, the `auth` object must be multi-service
    and multi-host aware.

    The exact form of the `auth` object is depending on the
    underlying connection object instantiated by the `ConnectionHook`
    that matches the target host.  For example, if the Python `requests`
    libarary is used for connections, the `auth` object is expected
    to be a callable such as `requests.auth.HTTPBasicAuth`.

    """

    def __init__(self, servicedef_manager, connection_manager):
        """ Create a `ServiceManager` to manager `Service` instances

        :param servicedef_manager: manager to create `ServiceDef`
            instances as needed
        :type ServiceDefManager: reschema.servicedef

        :param connection_manager: manager to establish connections to
            service hosts as needed
        :type ConnectionManager: sleepwalker.connection

        """
        self.servicedef_manager = servicedef_manager
        self.connection_manager = connection_manager

    def find_by_id(self, host, id, instance=None, auth=None):
        """ Find a Service object by service id.

        :param host: IP address or hostname
        :param id: fully qualified id of the service definition
        :param instance: unique instance identifier for this
            service relative to the same host
        :param auth: object representing authentication credentials

        """

        logger.info('ServiceManager instantiating new service: %s, %s, %s' %
                    (host, id, instance or '<no instance>'))
        servicedef = self.servicedef_manager.find_by_id(id)
        service = Service(servicedef, host=host, instance=instance,
                          service_manager=self,
                          connection_manager=self.connection_manager,
                          auth=auth)
        return service

    def find_by_name(self, host, name, version,
                     provider='riverbed', instance=None,
                     auth=None):
        """ Find a Service object by service <name,version,provider>

        :param host: the host for this service
        :param name: the service name
        :param version: the service version
        :param provider: the provider of the service
        :param instance: unique instance identifier for this
            service relative to the same host
        :param auth: object representing authentication credentials

        """
        servicedef = (self.servicedef_manager
                      .find_by_name(name, version, provider))
        service = Service(servicedef, host=host, instance=instance,
                          service_manager=self,
                          connection_manager=self.connection_manager,
                          auth=auth)
        return service


class Service(object):
    """ Manages all interaction with a server for a particular service.

    A `Service` instance is a client-side representation of
    a service hosted by a server as described by the following
    attributes:

    * service definition - the resources and operations supported
        by the service

    * host - the server hosting this service

    * instance - unique instance identifier

    * auth - an authentication object that is used for authentication
        requests to server

    Once created, most interaction with the server is done indirectly
    via `DataRep` instances associated with this `Service`.  The
    `bind()` method is used to lookup and bind to a resource, yielding
    a DataRep.

    """

    # Default api root for servicepath when not provided
    # by the user
    DEFAULT_ROOT = '/api'

    def __init__(self, servicedef, host, instance=None,
                 servicepath=None, service_manager=None,
                 connection=None, connection_manager=None,
                 auth=None):
        """ Create a Service object.

        :param servicedef: related ServiceDef for this Service

        :param host: schema + IP address or hostname + port

        :param instance: unique instance identifier for this
            service relative to the same host (by connection)

        :param servicepath: URI prefix excluding host/port
            for all resources for this service.  Defaults
            to /api/<instance>/<name>/<version>.

        :param service_manager: ServiceManager instance to use
            for finding other Services

        :param connection: connection to the target server
            to use for all API calls

        :param connection_manager: ConnectionManager instance to use
            for establishing a connection to other services

        :param auth: object representing authentication credentials
            to use for this service instance

        The `auth` object is opaque to the service object.  It is
        passed directly to the Connection class when a new connection
        is established.  If ConnectionManager is used, the auth is
        passed to the `ConnectionHook.connect()` method.

        """
        self.servicedef = servicedef
        self.host = host
        self.instance = instance
        if servicepath is None:
            # Default service path is built by joining
            # root, instance (if not null), name and version
            paths = [str(p) for p in [Service.DEFAULT_ROOT,
                                      instance,
                                      servicedef.name,
                                      servicedef.version] if p]

            servicepath = '/'.join(paths)

        self.servicepath = servicepath
        self.service_manager = service_manager
        self.connection = connection
        self.connection_manager = connection_manager
        self.auth = auth
        self.headers = {}

    def __repr__(self):
        return '<Service %s>' % self.servicedef.id

    def add_headers(self, headers):
        """ Add headers that are specific to this service. """
        self.headers.update(headers)

    def request(self, method, uri, body=None, params=None, headers=None):
        """ Make request through connection and return result. """
        if not self.connection:
            if not self.connection_manager:
                raise ServiceException('No connection defined for service.')

            self.connection = self.connection_manager.find(
                self.host, self.auth)

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

        :param _resource_name: resource to bind

        :param kwargs: variables specific to the resource to bind

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
        """ Look up a resource by name, and return a `Schema`. """
        return self._lookup(name, self.servicedef.find_resource,
                            ResourceException)

    def lookup_type(self, name):
        """ Look up a type by name, and return a `Schema`. """
        return self._lookup(name, self.servicedef.find_type, TypeException)
