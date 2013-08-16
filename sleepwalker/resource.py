# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import uritemplate
import copy
import logging

logger = logging.getLogger(__name__)

class MissingParameter(Exception): pass

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
            s = s + ' type ' + self.jsonschema.name
        return '<' + s + '>'
        
    def bind(self, **kwargs):
        selflink = self.jsonschema.links['self']
        vars = {}
        for var in uritemplate.variables(selflink.path.template):
            if var not in kwargs:
                raise MissingParameter('No value provided for parameter "%s" in self template: %s' %
                                       (var, selflink.path.template))

            vars[var] = kwargs[var]

        for var in kwargs:
            if var not in vars:
                raise ValueError('Invalid parameter "%s" for self template: %s' %
                                 (var, selflink.path.template))

        uri = selflink.path.resolve(vars)
        return Resource(self.service, uri, schema=self, data=vars)
    
class Resource(object):

    def __init__(self, service, uri, schema=None, data=None):
        self.uri = uri
        self.service = service
        self.schema = schema
        self.data = data
        
    def __repr__(self):
        s = 'Resource "%s"' % self.uri
        if self.schema:
            s = s + ' type ' + self.schema.jsonschema.name
        return '<' + s + '>'
        
    def __getattr__(self, key):
        if key in self.__dict__:
            return self.__dict__[key]

        if key in self.schema.jsonschema.links:
            link = self.schema.jsonschema.links[key]
            return lambda *args, **kwargs: self._follow(link, *args, **kwargs)

        raise AttributeError("No such attribute '%s'" % key)

    def _follow(self, link, *args, **kwargs):
        if link.path is not None:
            vars = copy.copy(self.data)

            # kwargs are used to ammed the data used to evaluate variables
            # in the link
            for key,value in kwargs.iteritems():
                vars[key] = value

            logger.debug("vars: %s" % vars)
            logger.debug("temp: %s" % link.path.template)
            # Determine the target path
            uri = link.path.resolve(vars)

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
                
            response = self.service.conn.json_request(uri, method, body, params)

            if ((uri == self.uri) and
                (link.response is not None) and
                (link.response.fullid() == self.schema.jsonschema.fullid())):
                self.data = response
                return self

            return Resource(self.service, uri, Schema(self.service, link.response), response)

        else:
            # Following a link to a target resource / link
            pass

        
        
