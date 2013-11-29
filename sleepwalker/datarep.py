# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

"""
Using :py:class:`DataRep` objects
---------------------------------

`DataRep` objects are the primary means of interacting with a 
REST server.  Each instance is associated with a URI defining the
address of the resource on the server, and optionally a json-schema
that describes the structure of the data.

There are a few ways to create `DataRep` instances:

* Use `Service.bind()` method - this looks up a resource by name
  in the rest-schema.

* Call `follow()` or `execute()` from another `DataRep` instance

* Create a new object via `create()` from a `DataRep` instance that
  supports creation.

Once created, a local copy of the data for this instance is retrieved
from the server via `pull()` and a the server is updated via `push()`.

A common read-modify-write cycle is shown below::

   >>> catalog = Service()
   >>> catalog.load_restschema('examples/Catalog.yml')
   >>> book = catalog.bind('book', id=1)
   >>> book
   <DataRep '/api/catalog/1.0/book' type book>

   # Retrieve a copy of the data from server
   >>> book.pull()

   # Examine the data retrieved
   >>> book.data
   { 'id': 1, 'title': 'My first book', 'author_ids': [1, 9], 'publisher_id': 3 }

   # Change the data
   >>> book.data['title'] = 'My First Book - Using Python'

   # Push the changes back to the server
   >>> book.push()

Links
-----

A schema may define one or more links the describe operations than can be
performed relative to an instance.  Each link is associated with a specific
HTTP method as described in the rest-schema.

For standard CRUD style resources, a resource will define get/set/create/delete
links.  Additional links that perform non-standard actions specific to that
resource may also be defined.

For example, consider the 'book' resource defined below::

   book:
      type: object
      properties:
         id: { type: number }
         title: { type: string }
         author_ids:
            type: array
            items: { type: number }
         publisher_id: { type: number }

      links:
         purchase:
            path: '$/books/{id}/purchase'
            method: POST

            request:
               type: object
               properties:
                  num_copies: { type: number }
                  shipping_address: { $ref: address }

            response:
               type: object
               properties:
                  delivery_date: { type: string }
                  final_cost: { type: number }

The `purchase` link describes how to purchase one or more copies of
this book.  In order to purchase 100 copies of book id=1, the client
must perform a POST to the server at the address
'/api/catalog/1.0/books/1/purchase' with a body include the requested
number of copies and shipping address.

Using a `DataRep` instance for this book, this is accomplished via the
`execute()` method::

   >>> book = catalog.bind('book', id=1)
   >>> request = {'num_copies': 100, 'shipping_address': '123 Street, Boston' }
   >>> response = book.execute('purchase', request)
   >>> response
   <DataRep '/api/catalog/1.0/books/1/purchase' type:book.links.purchase.response>

   >>> response.data
   { 'delivery_date': 'Oct 1', 'final_cost': 129.90 }

Calling `execute()` always returns a new `DataRep` instance representing the
response.

The list of links for a given `DataRep` is available by inspecting the
`links` property::

   >>> book.links.keys()
   ['self', 'get', 'set', 'delete', 'purchase', 'new_chapter']

Relations
---------

Relations provide the means to reach other resources that are related to
this one.  Each relation is essentially a pointer from one resource
to another.

For example, the `book` resource above has a `publisher_id` data
member.  This identifies the publisher associated with this book.  The
schema defines a relation 'publisher' that provides the link to the
full publisher resource::

   book:
      relations:
         publisher: 
            resource: publisher
            vars:
               id: '0/publisher_id'
   
This allows using the `follow()` method to get to a DataRep for the publisher::

   >>> pub = book.follow('publisher')
   >>> pub
   <DataRep '/api/catalog/1.0/publishers/3' type:publisher>

   >>> pub.data
   {'id': 3,
    'name': 'DigiPrinters',
    'billing_address': {'city': 'Boston', 'street': '123 Street'}
    }

The `follow` method use the `vars` property in the relation definition to
map the book.data['publisher_id'] value to the `id` variable in the
publisher representation, which is used to build the full URI.

Fragments
---------

In some cases, it may be necessary to follow links on data nested within
a single resource.  Consider the `book` example from above::

   >>> book
   >>> book.data
   { 'id': 1, 'title': 'My first book', 'author_ids': [1, 9], 'publisher_id': 3 }

   >>> book.data['author_ids']
   [1, 9]

Just like following the `publisher` link based on `publisher_id`, it's
possible to follow a link to reach an author resource.  However,
unlike publisher, there are multiple authors.

The schema defines the `full` relation to reach an author as follows::

   book:
      description: A book object
      type: object
      properties:
         id: { type: number }
         title: { type: string }
         publisher_id: { type: number }
         author_ids: 
            type: array
            items: 
               id: author_id
               type: number

               relations:
                  full:
                     resource: author
                     vars: { id: '0' }

The `publisher` relation was defined at the top-level at
`book.relations.publisher`.  The `full` relation is nested within
the structure at `book.properties.author_ids.items.relations.full`.
The best way to understand this is to look at the `type` at the same
level as the `relations` keywork.  In this case `relations.full` is
aligned with `type: number`.  This number is one author id in an
array of authors associated with this book.  That means that
the `full` relation must be invoked relative to an item in the
book.author_ids array.  The `full` reference indicates that
following this link will lead to a complete resource that is
represented in part by the current data member (the id)::

   >>> first_author = book['author_ids'][0].follow('full')
   >>> first_author
   <DataRep '/api/catalog/1.0/authors/1' type:author>

   >>> second_author = book['author_ids'][1].follow('full')
   >>> second_author
   <DataRep '/api/catalog/1.0/authors/9' type:author>

Breaking down that first line further shows DataRep fragment instances
created:

   >>> book.relations.keys()
   ['instances', 'publishers']
   
   >>> book_author_ids = book['author_ids']
   >>> book_author_ids
   <DataRep '/api/catalog/1.0/books/1#/author_ids' type:book.author_ids>

   >>> book_author_ids.data
   [1, 9]
   
   >>> book_author_ids_0 = book_author_ids[0]
   <DataRep '/api/catalog/1.0/books/1#/author_ids/0' type:book.author_ids[author_id]>
   
   >>> book_author_ids_0.relations.keys()
   ['full']

   >>> first_author = book_author_ids_0.follow('full')

Each time a `DataRep` instance is indexed using `[]`, a new DataRep
fragment is created.  This fragment is still associated with the same
URI because it is merely a piece of the data at that URI based
on the JSON pointer following the hash mark '#'.

"""

import copy
import logging
import uritemplate

from jsonpointer import resolve_pointer, set_pointer, JsonPointer
import reschema.jsonschema

from .exceptions import (MissingVar, InvalidParameter, RelationError,
                         FragmentError,
                         DataPullError, LinkError, DataNotSetError)

logger = logging.getLogger(__name__)

VALIDATE_REQUEST = True
VALIDATE_RESPONSE = False

class Schema(object):
    """ A Schema object represents the jsonschema for a resource or type.

    The Schema object is the generic form of a REST resource as defined by
    a json-schema.  If the json-schema includes a 'self' link, the bind()
    method may be used to instantiate concrete resources at fully defined
    addresses.  This class may also represent a `type` defined in
    the rest-schema.

    Typcially, a `Schema` instance is created via the `Service` class.
    This allows inspection of the jsonschema as well as to bind and create
    `DataRep` instances:

       >>> book_schema = catalog.lookup_schema('book')
       >>> book_schema
       <Schema '/api/catalog/1.0/books/{id}' type:book>

       >>> book_schema.jsonschema.validate({'id': 1})

       >>> book1 = book_schema.bind(id=1)
       >>> book1
       <DataRep '/api/catalog/1.0/books/1' type:book>

    """

    def __init__(self, service, jsonschema):
        """ Create a Schema bound to the given service as defined by jsonschema.
        :type service: sleepwalker.service.Service
        :type jsonschema: reschema.jsonschema.Schema subclass
        """
        self.service = service
        self.jsonschema = jsonschema
        
    def __repr__(self):
        s = 'Schema' 
        if 'self' in self.jsonschema.links:
            selflink = self.jsonschema.links['self']
            uri = selflink.path.template
            if uri[0] == '$':
                uri = selflink.api + uri[1:]
            s = s + " '" + uri + "'"
        s = s + ' type:' + self.jsonschema.fullname()
        return '<' + s + '>'
        
    def bind(self, **kwargs):
        """ Return a DataRep object by binding variables in the 'self' link.

        This method is used to instantiate concreate DataRep objects
        with fully qualified URIs based on the 'self' link associated
        with the jsonschema for this object.  The `**kwargs` must match
        the parameters defined in the self link, if any.

        Example::

           >>> book_schema = Schema(catalog, book_jsonschema)
           >>> book1 = book_schema.bind(id=1)
        
        """
        if 'self' not in self.jsonschema.links:
            raise LinkError("Cannot bind a schema that has no 'self' link")
        
        selflink = self.jsonschema.links['self']
        variables = {}
        for var in uritemplate.variables(selflink.path.template):
            if var not in kwargs:
                raise MissingVar(
                  'No value provided for variable "%s" in self template: %s' %
                  (var, selflink.path.template))

            variables[var] = kwargs[var]

        params = {}
        for var in kwargs:
            if var in selflink._params:
                params[var] = kwargs[var]
            elif var not in variables:
                raise InvalidParameter(
                  'Invalid parameter "%s" for self template: %s' %
                  (var, selflink.path.template))

        uri = selflink.path.resolve(variables)
        return DataRep(self.service, uri,
                       jsonschema=self.jsonschema, params=params)


class _DataRepValue(object):
    """ Internal class used to represent special DataRep.data states. """
    
    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return "<_DataRepValue %s>" % self.label

    
class DataRep(object):
    """ A concrete representation of a resource at a fully defined address.

    The DataRep object manages a data representation of a particular
    REST resource at a defined address.  If a jsonschema is attached,
    the jsonschema describes the structure of that data representation.

    """

    UNSET = _DataRepValue('UNSET')
    FAIL = _DataRepValue('FAIL')
    DELETED = _DataRepValue('DELETED')
    FRAGMENT = _DataRepValue('FRAGMENT')
    
    def __init__(self, service=None, uri=None, jsonschema=None,
                       fragment='', root=None,
                       data=UNSET, params=None):
        """ Creata a new DataRep object associated with the resource at `uri`.

        :param service: the service of which this resource is a part.
            :type service: sleepwalker.service.Service

        :param uri: the URI of the resource, without any fragment attached.
            If `fragment` and `root` are passed, this must be None and the URI
            is inherited from the root.
        :type uri: string
        
        :param jsonschema: a jsonschema.Schema derivative that describes the
            structure of the data at this uri.  If `fragment` and `root` are
            passed, this must be None, as the schema is inherited from the root.
        :type jsonschema: reschema.jsonschema.Schema subclass

        :param fragment: an optional JSON pointer creating a DataRep for
            a portion of the data at the given URI.  Requires `root` to be set.
        :type fragment: string

        :param root: must be set to the DataRep associated with the full
            data if `fragment` is set.
        :type root: DataRep

        :param data: optional, may be set to initialize the data value
            for this representation.  May not be used with `fragment`.
        :type data: Whatever Python data type matches the schema.

        :param params: is optional and defines additional parameters to use
            when retrieving the data represetnation from the server.  If
            specified, this instance shall be read-only.
        """
        # TODO: Should we allow fragment to take data and just assign it
        #       to the data *property* rather than _data?
        
        self.uri = uri
        self.service = service
        self.jsonschema = jsonschema
        self._data = data
        self.params = None if params == {} else params

        self.fragment = fragment
        self.root = root
        if fragment or root:
            if not root:
                raise FragmentError("Must supply root with fragment")
            elif not fragment:
                raise FragmentError("Must supply fragment with root")

            if (service or uri or jsonschema or params or
                data is not DataRep.UNSET):
                raise FragmentError(
                  "'fragment' and 'root' are the only valid arguments "
                  "when instantiating a fragment.")
            self._data = DataRep.FRAGMENT
            self.jsonschema = root.jsonschema[fragment]
            self.service = root.service
            self.uri = root.uri
            self.params = root.params

        elif not (service and uri and jsonschema):
            raise TypeError(
              "service, uri and jsonschema are required parameters")

        self.relations = self.jsonschema.relations
        self.links = self.jsonschema.links

        # Check if the 'get' link is supported and the link response
        # matches the jsonschema
        self._getlink = True
        if 'get' in self.links:
            l = self.links['get']
            resp = l.response
            if (not self.jsonschema.matches(resp)):
                self._getlink = (
                  "'get' link response does not match: %s vs %s" %
                  (resp, self.jsonschema))
        else:
            self._getlink = "No 'get' link for this resource"
            
        # Check if the 'set' link is supported and the link request and
        # response match the jsonschema
        self._setlink = True
        if 'set' in self.links:
            l = self.links['set']
            req = l.request
            resp = l.response
            if not (req and self.jsonschema.matches(req)):
                self._setlink = ("'set' link request does not match schema")
            elif not (resp and self.jsonschema.matches(resp)):
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
            if (not req.matches(resp)):
                self._createlink = (
                  "'create' link request does not match the response")
        else:
            self._createlink = "No 'create' link for this resource"
            
        # Check if the 'delete' link is supported
        self._deletelink = True
        if 'delete' not in self.links:
            self._deletelink = "No 'delete' link for this resource"
            
        
    def __repr__(self):
        s = "DataRep '%s" % self.uri
        if self.fragment:
            s += '#' + self.fragment
        s += "'"
        if self.params is not None:
            s += (" params:" +
                  ','.join(["%s=%s" % (key, value)
                            for (key,value) in self.params.iteritems()]))
        if self.jsonschema:
            s = s + ' type:' + self.jsonschema.fullname()
        return '<' + s + '>'

    def data_valid(self):
        """ Return True if the data property has a valid data representation. """
        return self._data not in [self.UNSET, self.FAIL, self.DELETED]
    
    def data_unset(self):
        """ Return True if the data property has not yet been set. """
        return self._data in [self.UNSET]
    
    @property
    def data(self):
        """ Return the data associated with this resource.

        This property serves as the client-side holder of the data
        associated the resource at the given address.  Calling `pull()`
        will refresh this propery with the latest data from the server.
        Calling `push()` will update the server with this data.
        
        If data has not yet been retrieved from the server, the first
        call to access this proprerty will result in a call to `pull()`
        Subsequent accesses will not refresh the data automatically,
        the client must manually invoke `pull()` as needed to refresh.

        
        If the last pull() resulted in a failure, an exception will be
        raised.

        If this DataRep instance defines a fragment, the data returned
        will be the result of following the fragment (as a JSON
        pointer) from the full data representation as the full URI.

        """
        if self._data is DataRep.FAIL:
            raise DataPullError("Last attempt to pull failed")

        if self._data is DataRep.DELETED:
            raise DataPullError("Resource was deleted")

        if self._data is DataRep.UNSET:
            self.pull()

        if self.fragment:
            return resolve_pointer(self.root.data, self.fragment)
        else:
            return self._data

    @data.setter
    def data(self, value):
        """ Modify the data associated for this resource.
        Note that while a root DataRep can be set without triggering a pull,
        setting a fragment requires accessing the fragment's root.data.
        """
        if self.fragment:
            set_pointer(self.root.data, self.fragment, value)
        else:
            self._data = value
        
    def pull(self):
        """ Retrieve a copy of the data representation for this resource from the server.

        This relies on the schema 'get' link.  This will always
        perform an interaction with the server to refresh the
        representation as per the 'get' link.
        
        On success, the result is cached in `self.data` and `self` is returned.

        """

        if self.root:
            self.root.pull()
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

        If `obj` is passed, `self.data` is modified.  This is true
        even if the push to the server results in a failure.
        
        On success, the `self` is returned

        Note that if this DataRep is associated with a fragment, the
        full data representation will be pushed to the server.
        
        """
        if self.root:
            if obj is not DataRep.UNSET:
                self.data = obj
            self.root.push()
            return self

        if self._setlink is not True:
            raise LinkError(self._setlink)

        if self.params is not None:
            raise LinkError(
              "push not allowed, DataRep with parameters is readonly")
            
        if obj is not DataRep.UNSET:
            self._data = obj

        if (not self.data_valid()):
            raise DataNotSetError("No data to push")

        if VALIDATE_REQUEST:
            self.jsonschema.validate(self._data)

        response = self.service.request('PUT', self.uri, self._data)
        self._data = response
        
        return self


    def create(self, obj):
        """ Create a new instance of a resource in a collection.

        This relies on the 'create' link in the json-schema.

        On success, this returns a new `DataRep` instance associated
        with the newly created resource.

        """

        if self._createlink is not True:
            raise LinkError(self._createlink)

        link = self.links['create']
        
        if VALIDATE_REQUEST:
            link.request.validate(obj)

        response = self.service.request('POST', self.uri, obj)
        logger.debug("create response: %s" % response)
        uri = link.response.links['self'].path.resolve(response)

        return DataRep(self.service, uri, jsonschema=link.response,
                       data=response)
    

    def delete(self):
        """ Issue a delete for this resource.

        This relies on the 'delete' link.

        On success, this marks the data property as DELETED and returns `self`.

        """

        if self._deletelink is not True:
            raise LinkError(self._deletelink)

        response = self.service.request('DELETE', self.uri)
        self._data = DataRep.DELETED
        return self


    def _resolve_path(self, path, **kwargs):
        """ Internal method to fill in path variables from data and kwargs. """
        # Need to make a copy of resource data, as we'll be adding kwargs
        # to this list and then resolving the path
        if self.data_valid() or self.data_unset():
            variables = copy.copy(self.data)

        # XXXCJ - what if self.data is an int?  How to merge in kwargs?
        for key, value in kwargs.iteritems():
            variables[key] = value

        if path is None:
            path = self.links['self'].path

        return path.resolve(variables)


    def follow(self, name, **kwargs):
        """ Follow a relation by name.

        `name` is the name of the relation to follow, and must exist in
        the jsonschema `relations`
        
        """
        if name not in self.relations:
            raise RelationError("%s has no relation '%s'" % (self, name))

        relation = self.relations[name]

        # The .data access checks and causes a pull if data is unset
        full_data = self.root.data if self.fragment else self.data
        (uri, params) = relation.resolve(full_data, self.fragment,
                                         params=kwargs)

        return DataRep(self.service, uri, jsonschema=relation.resource,
                       params=params)

    def execute(self, name, data=None, **kwargs):
        """ Execute a link by name.

        `name` is the link to follow and must exist in the jsonschema
        `links`

        `data` is used if the link defines a `request` object

        `kwargs` define additional parameters that may be required
        to fulfill the path 
        """
        if name not in self.jsonschema.links:
            raise LinkError("%s has no link '%s'" % (self, name))

        link = self.jsonschema.links[name]
        uri = self._resolve_path(link.path, **kwargs)
        method = link.method
        request_sch = link.request
        response_sch = link.response

        if method is None:
            raise LinkError(
              "%s: Unable to follow link '%s', no method defined" %
              (self, name))

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
        return DataRep(self.service, uri, jsonschema=response_sch,
                       data=response)

    
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
             'author_ids': [ 1, 9 ] }
           >>> book['id'].data
           101
           >>> book['author_ids'].data
           [ 1, 9]
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
            raise KeyError(key)

        return DataRep(fragment=self.fragment + '/' + str(key),
                       root=(self.root if self.root else self))
