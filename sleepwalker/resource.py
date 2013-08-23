# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import copy
import logging
import urlparse
import uritemplate
from functools import partial

from requests.sessions import merge_setting
from requests.packages.urllib3.util import parse_url

from .exceptions import MissingParameter, InvalidParameter, LinkError

logger = logging.getLogger(__name__)


class Schema(object):
    def __init__(self, service, jsonschema=None):
        self.service = service
        self.jsonschema = jsonschema
        
    def __repr__(self):
        s = 'Schema' 
        if self.jsonschema:
            if 'self' in self.jsonschema.links:
                selflink = self.jsonschema.links['self']
                s = s + ' "' + selflink.path.template + '"'
            s = s + ' type ' + self.jsonschema.fullname()
        return '<' + s + '>'
        
    def bind(self, **kwargs):
        selflink = self.jsonschema.links['self']
        variables = {}
        for var in uritemplate.variables(selflink.path.template):
            if var not in kwargs:
                raise MissingParameter('No value provided for parameter "%s" in self template: %s' %
                                       (var, selflink.path.template))

            variables[var] = kwargs[var]

        for var in kwargs:
            if var not in variables:
                raise InvalidParameter('Invalid parameter "%s" for self template: %s' %
                                       (var, selflink.path.template))

        uri = selflink.path.resolve(variables)
        if variables == {}:
            variables = None
        return Resource(self.service, uri, schema=self, data=variables)


class Links(object):
    """ Collection of resource links, initialized as property of Resource """
    def __init__(self, resource, links):
        self._resource = resource
        self._links = links

    def __getattr__(self, key):
        try:
            return partial(self._resource._follow, self._links[key])
        except KeyError:
            raise LinkError("No such link '%s' for resource %s" % 
                            (key, self._resource))

    def __getitem__(self, key):
        return self.__getattr__(key)

    def __repr__(self):
        return '<Resource %s links: %s>' % (self._resource.uri, 
                                            ','.join(self._links.keys()))

    def __str__(self):
        return str(self._links)

    def __contains__(self, key):
        return key in self._links

    def __dir__(self):
        return self._links.keys()
            

class Resource(object):

    def __init__(self, service, uri, schema=None, data=None):
        self.uri = uri
        self.service = service
        self.schema = schema
        self.data = data
        self.links = Links(self, self.schema.jsonschema.links)
        
    def __repr__(self):
        s = 'Resource "%s"' % self.uri
        if self.schema:
            s = s + ' type ' + self.schema.jsonschema.fullname()
        return '<' + s + '>'
        
    def __getattr__(self, key):
        if key in self.__dict__:
            return self.__dict__[key]

        raise AttributeError("No such attribute '%s'" % key)

    def _resolve_path(self, path=None, **kwargs):
        variables = copy.copy(self.data)

        if path is None:
            path = self.links['self'].path

        for key, value in kwargs.iteritems():
            variables[key] = value

        return path.resolve(variables)
    
    def _follow(self, link, data=None, validate=True, **kwargs):
        """ Validate and follow Resource links
        """
        if link.path is not None:
            uri = self._resolve_path(link.path, **kwargs)
        else:
            uri = None
            
        method = link.method
        if method is not None:
            if link.request is not None:
                # Validate the request
                link.request.validate(data)

            # Performing an HTTP transaction
            if method == "GET":
                params = data
                body = None
            elif method in ["POST", "PUT"]:
                params = None
                body = data
            else:
                params = None
                body = None
                
            response = self.service.request(method, uri, body, params)

            # Validate response by default
            if validate and link.response is not None:
                link.response.validate(response)

            # Check if the response is the same as this resource
            if ( (uri == self.uri) and 
                 (link.response is not None) and
                 link.response.isRef() and
                 (link.response.refschema.fullid() == self.schema.jsonschema.fullid())):
                self.data = response
                logger.debug("Updating data for %s from %s" % (self, method))
                logger.debug("...: %s" % response)
                return self

            return Resource(self.service, uri, Schema(self.service, link.response), response)

        elif link.target and not link.path:
            # Return target instance only
            return self.service.bind_resource(link.target_id, **kwargs)

        elif link.target and link.path:
            # Follow the path defined in the link, but only validate the response
            # as defined in the target
            method = link.target.method

            # uri resolved above will likely have params embedded
            parsed = parse_url(uri)
            uri = parsed.path
            uri_params = dict(urlparse.parse_qsl(parsed.query))

            if method == "GET":
                params = merge_setting(uri_params, data)
                body = None
            elif method in ["POST", "PUT"]:
                params = uri_params
                body = data
            else:
                params = None
                body = None

            response = self.service.request(method, uri, body, params)

            # Validate response by default
            if validate and link.target.response is not None:
                link.target.response.validate(response)

            return Resource(self.service, uri, Schema(self.service, link.target.response), response)

        else:
            raise LinkError('Unable to determine link to follow')

    def get(self, params=None, **kwargs):
        """Retrieve a copy of the data representation for this resource from the server.

        If the schema defines a 'get' link, that is used.  Otherwise a simple HTTP GET
        is invoked.  On succeuss, the result is cached in self.data and returned."""

        if 'get' in self.links:
            self.links.get(params, **kwargs)
            return self.data

        response = self.service.request('GET', self.uri)
        self.data = response

        return response
