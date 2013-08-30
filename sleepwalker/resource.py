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

VALIDATE_REQUEST = True
VALIDATE_RESPONSE = False

class Schema(object):
    """ A Schema object manages access to the schema for a class of resource.

    The Schema object is the generic form of a REST resource as defined by
    a json-schema.  If the json-schema includes a 'self' link, the bind()
    method may be used to instantiate conrete resources at fully defined
    addresses.

    """

    def __init__(self, service, jsonschema):
        """ Create a Schema bound to the given service as defined by jsonschema. """
        self.service = service
        self.jsonschema = jsonschema

        
    def __repr__(self):
        s = 'Schema' 
        if 'self' in self.jsonschema.links:
            selflink = self.jsonschema.links['self']
            s = s + ' "' + selflink.path.template + '"'
        s = s + ' type ' + self.jsonschema.fullname()
        return '<' + s + '>'
        
    def bind(self, **kwargs):
        """ Return a Resource object by binding variables in the 'self' link.

        This method is used to instantiate concreate Resource objects
        with fully qualified URIs based on the 'self' link associated
        with the jsonschema for this object.  The **kwargs must match
        the parameters defined in the self link, if any.

        Example:
        >>> book_schema = Schema(service, book_jsonschema)
        >>> book1 = book_schema.bind(id=1)
        
        """
        if 'self' not in self.jsonschema.links:
            raise LinkError("Cannot bind a schema that has no 'self' link")
        
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


class _Links(object):
    """ Collection of resource links, initialized as property of Resource.

    The list of possible links is derived directly from the jsonschema
    links property.  Each link name is callable directly as a method.

    The primary use of the links object is via the resource 'links' property:
    >>> resource.links.<linkname>(<args>)

    This is identical to the following:
    >>> resource.follow(<linkname>, <args>)

    As an object, this supports autocompletion and inspection.

    """
    
    def __init__(self, resource):
        self._resource = resource
        self._links = resource.schema.jsonschema.links

    def __getattr__(self, key):
        return partial(self._resource.follow, key)

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
    """ A concrete representation of a resource at a fully defined address.

    The Resource object manages interaction with a REST resource at a
    defined address.  If a schema is attached, the schema describes the
    abstract resource definition via a jsonschema.

    """

    def __init__(self, service, uri, schema=None, data=None):
        self.uri = uri
        self.service = service
        self.schema = schema
        self.data = data
        self.links = _Links(self)
        
    def __repr__(self):
        s = 'Resource "%s"' % self.uri
        if self.schema:
            s = s + ' type ' + self.schema.jsonschema.fullname()
        return '<' + s + '>'
        
    def _resolve_path(self, path=None, **kwargs):
        variables = copy.copy(self.data)

        if path is None:
            path = self.links['self'].path

        for key, value in kwargs.iteritems():
            variables[key] = value

        return path.resolve(variables)

    def follow(self, linkname, data=None, **kwargs):
        """ Follow a link by name. """
        if linkname not in self.schema.jsonschema.links:
            raise LinkError("%s has no link '%s'" % (self, linkname))

        link = self.schema.jsonschema.links[linkname]

        if link.path is not None:
            uri = self._resolve_path(link.path, **kwargs)
        else:
            uri = None
            
        method = link.method
        if method is not None:
            if VALIDATE_REQUEST and link.request is not None:
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

            # Validate response 
            if VALIDATE_RESPONSE and link.response is not None:
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

            # Validate response
            if VALIDATE_RESPONSE and link.target.response is not None:
                link.target.response.validate(response)

            return Resource(self.service, uri, Schema(self.service, link.target.response), response)

        else:
            raise LinkError("%s: Unable to follow link '%s', invalid definition")

    def get(self, params=None, **kwargs):
        """ Retrieve a copy of the data representation for this resource from the server.

        This relies on the schema 'get' link.  This will always
        perform an interaction with the server to refresh the
        representation as per the 'get' link.  Any keyword arguments
        are passed as URI parameters and must conform to the
        'links.get.request' defintion in the schema.
        
        On success, the result is cached in self.data and returned.

        """

        if 'get' not in self.links:
            raise LinkError("Resource does not support 'get' link")

        self.links.get(params, **kwargs)
        return self.data

    def set(self, obj):
        """ Modify the data representation for this resource from the server.

        This relies on the schema 'set' link.  This will always
        perform an interaction with the server to attempt an update
        of the representation as per the 'set' link.  Any keyword
        arguments are passed as URI parameters and must conform to the
        'links.get.request' defintion in the schema.
        
        On success, the result is cached in self.data and returned.

        """
        pass

    def __getitem__(self, key):
        """ Index into the resource object following the schema structure.
        """
        return self.subresource(key)

    def subresource(self, prop):
        """ Index into the resource based on the structure of the data representation.

        This method allows indexing into a single resource to allow accessing
        nested links and data.

        Example:
        >>> book = Resource(...)
        >>> book.links.get()
        >>> book.data
        { 'id': 101,
          'title': 'My book',
          'author_ids': [ 1, 2 ] }
        >>> book['id'].data
        101
        >>> book['author_ids'].data
        [ 1, 2]
        >>> book['author_ids'][0].data
        1
        >>> author = book['author_ids'][0].links.author()
        >>> author.get()
        >>> author.data
        { 'id' : 1,
          'name' : 'John Doe' }

        """
        # XXXCJ - this could return an Resource object with a fragment representing the
        #   nested data element, or maybe a SubResource object (new class)
        
        pass
        
        
   
        
