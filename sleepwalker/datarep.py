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

from jsonpointer import resolve_pointer, set_pointer, JsonPointer
import reschema.jsonschema

from .exceptions import MissingParameter, InvalidParameter, RelationError, DataPullError, LinkError

logger = logging.getLogger(__name__)

VALIDATE_REQUEST = True
VALIDATE_RESPONSE = False

class Schema(object):
    """ A Schema object manages access to the schema for a class of resource.

    The Schema object is the generic form of a REST resource as defined by
    a json-schema.  If the json-schema includes a 'self' link, the bind()
    method may be used to instantiate concrete resources at fully defined
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
        """ Return a DataRep object by binding variables in the 'self' link.

        This method is used to instantiate concreate DataRep objects
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

        params = {}
        for var in kwargs:
            if selflink.request and var in selflink.request.props:
                params[var] = kwargs[var]
            elif var not in variables:
                raise InvalidParameter('Invalid parameter "%s" for self template: %s' %
                                       (var, selflink.path.template))

        uri = selflink.path.resolve(variables)
        return DataRep(self.service, uri, jsonschema=self.jsonschema, params=params)


class _DataRepValue(object):
    """ Internal class used to represent special DataRep.data states. """
    
    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return "<_DataRepValue %s>" % self.label

    
class DataRep(object):
    """ A concrete representation of a resource at a fully defined address.

    The DataRep object manages interaction with a REST resource at a
    defined address.  If a jsonschema is attached, the jsonschema describes the
    abstract resource definition via a jsonschema.

    """

    UNSET = _DataRepValue('UNSET')
    FAIL = _DataRepValue('FAIL')
    
    def __init__(self, service, uri, fragment=None, parent=None,
                 jsonschema=None, data=UNSET, params=None):
        """ Creata a new DataRep object at the address `uri`.

        `fragment` is an optional JSON pointer creating a DataRep for
        a portion of the data at the given URI.

        `parent` must be set to the DataRep associated with the full
        data if `fragment` is set
        
        `jsonschema` is a jsonschema.Schema derivative that describes the
        structure of the data at this uri.  If `fragment` is not null, the
        `jsonschema` must represent the `fragment`, not the entire data.

        `data` is optional and may be set to initialize the data value
        for this representation.  If `fragment` is also passed, `data` must
        be the complete data representation for the URI, and `fragment` a
        valid JSON pointer indexing into that data.

        `params` is optional and defines additional parameters to use
        when retrieving the data represetnation from the server.  If
        specified, this instance shall be read-only.

        """
        
        self.uri = uri
        self.service = service
        self.jsonschema = jsonschema
        self._data = data
        self.fragment = fragment
        self.parent = parent
        self.params = None if params == {} else params

        self.relations = self.jsonschema.relations
        self.links = self.jsonschema.links

        # Check if the 'get' link is supported and the link response
        # matches the jsonschema
        self._getlink = True
        if 'get' in self.links:
            l = self.links['get']
            resp = l.response
            if (resp is not self.jsonschema):
                self._getlink = ("'get' link response does not match: %s vs %s" %
                                 (resp, self.jsonschema))
        else:
            self._setlink = "No 'get' link for this resource"
            
        # Check if the 'set' link is supported and the link request and
        # response match the jsonschema
        self._setlink = True
        if 'set' in self.links:
            l = self.links['set']
            req = l.request
            resp = l.response
            if not (req and req is self.jsonschema):
                self._setlink = ("'set' link request does not match schema")
            elif not (resp and resp is self.jsonschema):
                self._setlink = ("'set' link response does not match schema")
        else:
            self._setlink = "No 'set' link for this resource"

        # Check if the 'create' link is supported and the link request and
        # response match the jsonschema
        self._createlink = True
        if 'create' in self.links:
            l = self.links['create']
            req = l.request
            resp = l.response
            if (req is not resp):
                self._createlink = "'create' link request does not match the response"
        else:
            self._createlink = "No 'create' link for this resource"
            
        # Check if the 'delete' link is supported
        self._deletelink = True
        if 'delete' not in self.links:
            self._deletelink = "No 'delete' link for this resource"
            
        
    def __repr__(self):
        s = 'DataRep "%s' % self.uri
        if self.fragment:
            s += '#' + self.fragment
        s += '"'
        if self.params is not None:
            s += " params:" + ','.join(["%s=%s" % (key, value) for (key,value) in self.params.iteritems()])
        if self.jsonschema:
            s = s + ' type:' + self.jsonschema.fullname()
        return '<' + s + '>'
        
    @property
    def data(self):
        """ Return the data associated for this resource.

        Accessing the data property will cause a pull() if the data
        has not been previously accessed.  If the last pull() resulted
        in a failure, an exception will be raised.

        If this DataRep defines a fragment, the data returned will be
        the result of following the fragment (as a JSON pointer) from
        the full data representation as the full URI.
        """
        if self._data is DataRep.FAIL:
            raise DataPullError("Last attept to pull failed")

        if self._data is DataRep.UNSET:
            self.pull()

        if self.fragment:
            return resolve_pointer(self._data, self.fragment)
        else:
            return self._data

    @data.setter
    def data(self, value):
        """ Modify the data associated for this resource. """
        if self.fragment:
            set_pointer(self._data, self.fragment, value)
        else:
            self._data = value
        
    def _resolve_path(self, path, **kwargs):
        """ Internal method to fill in path variables from data and kwargs. """
        # Need to make a copy of resource data, as we'll be adding kwargs
        # to this list and then resolving the path
        variables = copy.copy(self.data)

        # XXXCJ - what if self.data is an int?  How to merge in kwargs?
        for key, value in kwargs.iteritems():
            variables[key] = value

        if path is None:
            path = self.links['self'].path

        return path.resolve(variables)

    def follow(self, name, data=None, **kwargs):
        """ Follow a relation by name. """
        if name not in self.relations:
            raise RelationError("%s has no relation '%s'" % (self, name))

        relation = self.relations[name]

        (uri, params) = relation.resolve(self._data, self.fragment, params=kwargs)
                    
        return DataRep(self.service, uri, jsonschema=relation.resource, params=params)

    def execute(self, name, data=None, **kwargs):
        """ Execute a link by name. """
        if name not in self.jsonschema.links:
            raise LinkError("%s has no link '%s'" % (self, name))

        link = self.jsonschema.links[name]
        uri = self._resolve_path(link.path, **kwargs)
        method = link.method
        request_sch = link.request
        response_sch = link.response

        if method is None:
            raise LinkError("%s: Unable to follow link '%s', no method defined")

        if VALIDATE_REQUEST and request_sch is not None:
            # Validate the request
            request_sch.validate(data)

        # Performing an HTTP transaction
        if method == "GET":
            # XXXCJ - merge in kwargs?
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
        if VALIDATE_RESPONSE and response_sch is not None:
            response_sch.validate(response)

        # Create a DataRep for the response
        return DataRep(self.service, uri, jsonschema=response_sch, data=response)


    def pull(self):
        """ Retrieve a copy of the data representation for this resource from the server.

        This relies on the schema 'get' link.  This will always
        perform an interaction with the server to refresh the
        representation as per the 'get' link.
        
        On success, the result is cached in self.data and self is returned.

        """

        if self.parent:
            self.parent.pull()
            return self
        
        if self._getlink is not True:
            raise LinkError(self._getlink)

        response = self.service.request('GET', self.uri, params=self.params)
        self._data = response
        return self


    def push(self, obj=UNSET):
        """ Modify the data representation for this resource from the server.

        This relies on the schema 'set' link.  This will always
        perform an interaction with the server to attempt an update
        of the representation as per the 'set' link.

        If `obj` is passed, self.data is modified.
        
        On success, the self is returned

        """
        if self.parent:
            if obj is not DataRep.UNSET:
                self.data = obj
            self.parent.push()
            return self

        if self._setlink is not True:
            raise LinkError(self._setlink)

        if self.params is not None:
            raise LinkError("push not allowed, DataRep with parameters is readonly")
            
        if obj is not DataRep.UNSET:
            self._data = obj

        if (self._data is DataRep.UNSET or
            self._data is DataRep.FAIL):
            raise DataNotSetError("No data to push")

        if VALIDATE_REQUEST:
            self.jsonschema.validate(self._data)

        response = self.service.request('PUT', self.uri, self._data)
        self._data = response
        
        return self


    def create(self, obj):
        """ Create a new instance of a resource in a collection.

        This relies on the 'create' link.

        """

        if self._createlink is not True:
            raise LinkError(self._createlink)

        link = self.links['create']
        
        if VALIDATE_REQUEST:
            link.request.validate(obj)

        response = self.service.request('POST', self.uri, obj)
        logger.debug("create response: %s" % response)
        uri = link.response.links['self'].path.resolve(response)

        return DataRep(self.service, uri, jsonschema=link.response, data=response)
    

    def delete(self):
        """ Issue a delete for this resource.

        This relies on the 'delete' link.

        """

        if self._deletelink is not True:
            raise LinkError(self._deletelink)

        response = self.service.request('DELETE', self.uri)
        self._data = DataRep.UNSET
        return self

    
    def __getitem__(self, key):
        """ Index into the datarep based on the structure of the data representation.

        This method allows indexing into a single datarep to allow accessing
        nested links and data.

        Example:
        >>> book = DataRep(...)
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
        js = self.jsonschema
        
        if isinstance(js, reschema.jsonschema.Object):
            if key not in self.data:
                raise KeyError(key)
            
        elif isinstance(js, reschema.jsonschema.Array):
            try:
                key = int(key)
            except:
                raise KeyError(key)

            if key < 0 or key >= len(self.data):
                raise IndexError(key)
        else:
            return KeyError(key)

        return DataRep(self.service, self.uri, fragment=(self.fragment or '') + '/' + str(key),
                       jsonschema=self.jsonschema[key], data=self._data, parent=self)
