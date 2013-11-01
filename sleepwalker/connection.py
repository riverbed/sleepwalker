# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import ssl
import json
import urlparse

import requests
import requests.exceptions
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from requests.packages.urllib3.util import parse_url
from requests.packages.urllib3.poolmanager import PoolManager

from .exceptions import ConnectionError, URLError


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


class Connection(object):
    """ Handle authentication and communication to remote machines. """
    def __init__(self, hostname, auth=None, port=None, verify=True):
        """ Initialize new connection and setup authentication

            `hostname` - include protocol, e.g. "https://host.com"
            `auth` - authentication object, see below
            `port` - optional port to use for connection
            `verify` - require SSL certificate validation.

            Authentication:
            For simple basic auth, passing a tuple of (user, pass) is
            sufficient as a shortcut to an instance of HTTPBasicAuth.
            This auth method will trigger a check  to ensure
            the protocol is using SSL to connect (though cert verification
            may still be turned off to avoid errors with self-signed certs).

            OAuth2 will require the ``requests-oauthlib`` package and
            an instance of the `OAuth2Session` object.

            netrc config files will be checked if auth is left as None.
            If no authentication is provided for the hostname in the
            netrc file, or no file exists, an error will be raised
            when trying to connect.
        """
        p = parse_url(hostname)
        if not p.scheme:
            raise URLError('Scheme must be provided (e.g. https:// or http://).')
        else:
            if p.port and port and p.port != port:
                raise URLError('Mismatched ports provided.')
            elif not p.port and port:
                hostname = hostname + ':' + str(port)

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

    def _request(self, method, uri, body=None, params=None, extra_headers=None):
        p = parse_url(uri)
        if not p.host:
            uri = self.get_url(uri)

        try:
            r = self.conn.request(method, uri, data=body, params=params, headers=extra_headers)
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
            if self._ssladapter:
                # If we've already applied an adapter, this is another problem
                raise

            # Otherwise, mount adapter and retry the request
            self.conn.mount('https://', SSLAdapter(ssl.PROTOCOL_TLSv1))
            self._ssladapter = True
            r = self.conn.request(method, uri, data=body, params=params, headers=extra_headers)

        self.response = r

        # check if good status response otherwise raise exception
        if not r.ok:
            r.raise_for_status()

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

    def json_request(self, method, uri, body=None, params=None, extra_headers=None):
        """ Send a JSON request and receive JSON response. """
        if extra_headers:
            extra_headers = CaseInsensitiveDict(extra_headers)
        else:
            extra_headers = CaseInsensitiveDict()
        extra_headers['Content-Type'] = 'application/json'
        extra_headers['Accept'] = 'application/json'
        if body:
            body = json.dumps(body, cls=self.JsonEncoder)
        r = self._request(method, uri, body, params, extra_headers)
        if r.status_code == 204 or len(r.content) == 0:
            return None  # no data
        return r.json()

    def add_headers(self, headers):
        self.conn.headers.update(headers)
