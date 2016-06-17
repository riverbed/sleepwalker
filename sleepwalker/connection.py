# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

"""
This module defines the `ConnectionManager` class which is used
together with `ServiceManager` class to support seamlessly following
links and relations from one service to another, whether on the
same host or on different hosts.

A single `ConnectionManager` instance instantiates connections
to target hosts by calling registered `ConnectionHook` instances.
A connection is established for each unique <host, auth> pair,
where the auth object represents the authentication credentials
in a form understood by the underlying connection class.

"""

import ssl
import json
import urlparse
import logging
import requests
import requests.exceptions
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from requests.packages.urllib3.util import parse_url
from requests.packages.urllib3.poolmanager import PoolManager
from collections import Iterable

from sleepwalker.exceptions import URLError, HTTPError, ConnectionError

logger = logging.getLogger(__name__)


class SSLAdapter(HTTPAdapter):
    """ An HTTPS Transport Adapter that uses an arbitrary SSL version. """
    # handle https connections that don't like to negotiate
    # see https://lukasa.co.uk/2013/01/Choosing_SSL_Version_In_Requests/
    def __init__(self, ssl_version=None, **kwargs):
        self.ssl_version = ssl_version

        super(SSLAdapter, self).__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       ssl_version=self.ssl_version)


class ConnectionHook(object):
    """ This class defines the interface for establshing connections for ConnectionManager.

    This class must be sub-classed and the `connect()` method
    implemented.  An instance of the new class is passed to the
    `ConnectionManager.add_conn_hook()` method.

    """

    def connect(self, host, auth):
        """ Establish a new Connection to the target host.

        :param host: scheme / ip address or hostname / port of the
            target server to connect to
        :param auth: object representing authentication credentials
            to use for requests to the target host

        This method must return a `Connection` object (or similar) or
        None if this hook does not know how to connect to the named
        `host`.

        """
        return Connection(host, auth)


class ConnectionManager(object):

    _default_hooks = [ConnectionHook()]

    def __init__(self):
        # Index of connections by host
        self.conns = {}

        # List of connection hooks to use
        self._conn_hooks = []

    def add(self, host, auth, conn):
        """ Manually add a connection to the given host to the manager.

        :param host: the target host of the connection
        :param auth: object representing authentication credentials
        :param conn: a `Connection` object

        Note that if a connection is already present to the target host
        it is replaced with the new connection.

        """
        self.conns[(host, auth)] = conn

    def add_conn_hook(self, hook):
        """ Add a connection hook to call to establish new connections. """
        self._conn_hooks.append(hook)

    def clear_hooks(self):
        """ Drop all connection hooks. """
        self._conn_hooks = []

    def reset(self):
        """ Close and forget all connections. """
        for conn in self.conns.values():
            conn.close()
        self.conns = {}

    def find(self, host, auth):
        """ Find a connection to the given host, trying hooks as needed.

        :param host: the target host of the connection
        :param auth: object representing authentication credentials

        :raises ConnectionError: if no connection to the target host
           could be found and no connection hooks succeeded in
           establishing a new connection
        """
        key = (host, auth)
        if key not in self.conns:
            conn = None
            hooks = self._conn_hooks or self._default_hooks
            for hook in hooks:
                conn = hook.connect(host, auth)
                if conn:
                    logger.info("Established new connection to '%s' via '%s'" %
                                (host, hook))
                    break
            if conn is None:
                raise ConnectionError(
                    'Failed to establish a connection to %s' % host)
            self.add(host, auth, conn)
        else:
            conn = self.conns[key]
            logger.debug("Reusing existing connection to '%s'" % (host))
        return conn


class Connection(object):

    """ Handle authentication and communication to remote machines. """
    def __init__(self, hostname, auth=None, port=None, verify=True,
                 timeout=None):
        """ Initialize new connection and setup authentication

            `hostname` - include protocol, e.g. 'https://host.com'
            `auth` - authentication object, see below
            `port` - optional port to use for connection
            `verify` - require SSL certificate validation.
            `timeout` - float connection timeout in seconds, or tuple
                        (connect timeout, read timeout)

            Authentication:
            For simple basic auth, passing a tuple of (user, pass) is
            sufficient as a shortcut to an instance of HTTPBasicAuth.
            This auth method will trigger a check  to ensure
            the protocol is using SSL to connect (though cert verification
            may still be turned off to avoid errors with self-signed certs).

            netrc config files will be checked if auth is left as None.
            If no authentication is provided for the hostname in the
            netrc file, or no file exists, an error will be raised
            when trying to connect.
        """
        p = parse_url(hostname)
        if not p.scheme:
            raise URLError('Scheme must be provided (e.g. https:// '
                           'or http://).')
        else:
            if p.port and port and p.port != port:
                raise URLError('Mismatched ports provided.')
            elif not p.port and port:
                hostname = hostname + ':' + str(port)

        # since the system re-tries, the effective timeout
        # will be 2 times the connection timeout specified, so divide
        # it in half so the connection timeout is what the caller expects
        if timeout is None:
            self.timeout = None
        elif isinstance(timeout, Iterable):
            if len(timeout) != 2:
                raise ValueError('timeout tuple must be 2 float entries')
            self.timeout = tuple([float(timeout[0]) / 2.0,
                                  float(timeout[1])])
        else:
            self.timeout = float(timeout) / 2.0

        self.hostname = hostname
        self._ssladapter = False

        self.conn = requests.session()
        self.conn.auth = auth
        self.conn.verify = verify

        # store last full response
        self.response = None

    def get_url(self, uri):
        """ Returns a fully qualified URL given a URI. """
        # TODO make this a prepend_if_needed type method
        return urlparse.urljoin(self.hostname, uri)

    def _request(self, method, uri, body=None, params=None,
                 extra_headers=None):
        p = parse_url(uri)
        if not p.host:
            uri = self.get_url(uri)

        try:
            r = self.conn.request(method, uri, data=body, params=params,
                                  headers=extra_headers, timeout=self.timeout)
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError) as e:
            if self._ssladapter:
                # If we've already applied an adapter, this is another problem
                # Raise the corresponding sleepwaker exception.
                raise ConnectionError("Could not connect to uri %s: %s",
                                      uri, e)

            # Otherwise, mount adapter and retry the request
            self.conn.mount('https://', SSLAdapter(ssl.PROTOCOL_TLSv1))
            self._ssladapter = True
            r = self.conn.request(method, uri, data=body, params=params,
                                  headers=extra_headers, timeout=self.timeout)

        self.response = r

        # check if good status response otherwise raise exception
        if not r.ok:
            HTTPError.raise_by_status(r)

        return r

    class JsonEncoder(json.JSONEncoder):
        """ Handle more object types if first encoding doesn't work. """
        def default(self, obj):
            try:
                res = super(Connection.JsonEncoder, self).default(obj)
            except TypeError:
                try:
                    res = obj.to_dict()
                except AttributeError:
                    res = obj.__dict__
            return res

    def json_request(self, method, uri, body=None, params=None,
                     extra_headers=None):
        """ Send a JSON request and receive JSON response. """
        if extra_headers:
            extra_headers = CaseInsensitiveDict(extra_headers)
        else:
            extra_headers = CaseInsensitiveDict()
        extra_headers['Content-Type'] = 'application/json'
        extra_headers['Accept'] = 'application/json'
        if body is not None:
            body = json.dumps(body, cls=self.JsonEncoder)
        r = self._request(method, uri, body, params, extra_headers)
        if r.status_code == 204 or len(r.content) == 0:
            return None  # no data
        return r.json()

    def add_headers(self, headers):
        """ Add headers that are common to all requests. """
        self.conn.headers.update(headers)
