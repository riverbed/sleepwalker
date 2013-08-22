# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import json
import urlparse

import requests
from requests.utils import prepend_scheme_if_needed
from requests.packages.urllib3.util import parse_url
from requests.structures import CaseInsensitiveDict

from .exceptions import ConnectionError, URLError


class Connection(object):
    """ Handle authentication and communication to remote machines
    """
    def __init__(self, hostname, auth=None, port=None, verify=True):
        """ Initialize new connection and setup authentication

            `hostname` - include protocol, e.g. "https://host.com"
                         or override port using `port` kwarg
            `auth` - authentication object, see below
            `port` - optionally call out the port explicitly.  Ports
                     80 and 443 will map to schemes 'http' and 'https',
                     respectively.  Other ports will use 'https' if 
                     no scheme included in the hostname.
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
            if str(port) == '80':
                scheme = 'http'
            elif str(port) == '443':
                scheme = 'https'
            else:
                scheme = 'https'
                if p.port and port and p.port != port:
                    # ports don't match
                    raise URLError('Mismatched ports provided.')
                elif not p.port and port:
                    hostname = hostname + ':' + str(port)
                else:
                    # nothing to do
                    pass
            hostname = prepend_scheme_if_needed(hostname, scheme)

        self.hostname = hostname

        self.conn = requests.session()
        self.conn.auth = auth
        self.conn.verify = verify

        # store last full response
        self.response = None

    def get_url(self, uri):
        """ Returns a fully qualified URL given a URI
        """
        # TODO make this a prepend_if_needed type method
        return urlparse.urljoin(self.hostname, uri)

    def _request(self, method, uri, body=None, params=None, extra_headers=None):
        p = parse_url(uri)
        if not p.host:
            uri = self.get_url(uri)

        r = self.conn.request(method, uri, data=body, params=params, headers=extra_headers)
        self.response = r

        # check if good status response otherwise raise exception
        if not r.ok:
            r.raise_for_status()

        return r

    class JsonEncoder(json.JSONEncoder):
        """ Handle more object types if first encoding doesn't work
        """
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
        """ Send a JSON request and receive JSON response
        """
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
