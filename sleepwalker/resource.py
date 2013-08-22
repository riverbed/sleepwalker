# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import uritemplate
import copy
import logging
from functools import partial

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


class Resource(object):

    def __init__(self, service, uri, schema=None, data=None):
        self.uri = uri
        self.service = service
        self.schema = schema
        self.data = data
        
    def __repr__(self):
        s = 'Resource "%s"' % self.uri
        if self.schema:
            s = s + ' type ' + self.schema.jsonschema.fullname()
        return '<' + s + '>'
        
    def __getattr__(self, key):
        if key in self.__dict__:
            return self.__dict__[key]

        raise AttributeError("No such attribute '%s'" % key)

    @property
    def links(self):
        class Links(object):
            def __init__(self, resource, links):
                self.resource = resource
                self.links = links
            def __getattr__(self, key):
                if key in self.links:
                    return partial(self.resource._follow, self.links[key])
                else:
                    raise LinkError("No such link '%s' for resource %s" % 
                                    (key, self.resource))
            def __repr__(self):
                return str(self.links)
            def __contains__(self, key):
                return key in self.links
            
        return Links(self, self.schema.jsonschema.links)

    def _resolve_path(self, path=None, **kwargs):
        variables = copy.copy(self.data)

        if path is None:
            path = self.links['self'].path

        for key, value in kwargs.iteritems():
            variables[key] = value

        return path.resolve(variables)
    
    def _follow(self, link, *args, **kwargs):
        if link.path is not None:
            uri = self._resolve_path(link.path, **kwargs)
        else:
            uri = None
            
        method = link.method
        if method is not None:
            if link.request is not None:
                # Validate the request
                link.request.validate(args[0])

            # Performing and HTTP transaction
            if method == "GET":
                params = args[0] if len(args) > 0 else None
                body = None
            elif method in ["POST", "PUT"]:
                params = None
                body = args[0]
            else:
                params = None
                body = None
                
            response = self.service.connection.json_request(method, uri, body, params)

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

        else:
            # Following a link to a target resource / link
            pass

    def get(self, params=None, **kwargs):
        """Retrieve a copy of the data representation for this resource from the server.

        If the schema defines a 'get' link, that is used.  Otherwise a simple HTTP GET
        is invoked.  On succeuss, the result is cached in self.data and returned."""

        if 'get' in self.links:
            self.links.get(params, **kwargs)
            return self.data

        response = self.service.connection.json_request('GET', self.uri)
        self.data = response

        return response
