# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import os
import re
import string
import logging
import unittest
import copy

import uritemplate
from reschema.jsonschema import Ref

from sleepwalker.service import Service
from sleepwalker.datarep import DataRep
from sleepwalker.connection import Connection

from sim_connection import SimConnection

logger = logging.getLogger(__name__)

TEST_PATH = os.path.abspath(os.path.dirname(__file__))

class CatalogConnection(SimConnection):
    def __init__(self, test=None):
        SimConnection.__init__(self, test)
        self.add_collection('books', 'book')
        self.add_collection('authors', 'author')
        self.add_collection('publishers', 'publisher')

    def books_links_get(self, link, method, uri, data, params, headers):
        result = []
        for v in self._collections['books'].values():
            add = True
            if params:
                for p,pv in params.iteritems():
                    if p == 'author' and pv not in v['author_ids']:
                        add = False
                        break
            if add:
                result.append({'id': v['id'], 'title': v['title']})
        return result

    def book_links_purchase(self, link, method, uri, data, params, headers):
        response = {'delivery_date' : 'Oct 1', 'final_cost': data['num_copies'] * 12.99}
        return response
        
class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.service.load_servicedef(os.path.join(TEST_PATH, "Catalog.yml"))
        self.service.connection = CatalogConnection(self)
        self.service.connection.add_servicedef(self.service.servicedef)

    def test_catalog(self):
        authors = self.service.bind('authors')
        harry = authors.create({'name': 'Harry'})
        fred = authors.create({'name': 'Fred'})

        books = self.service.bind('books')
        for i in range(3):
            books.create({'title': 'Harry - book %d' % i, 'author_ids': [harry.data['id']]})

        for i in range(4):
            books.create({'title': 'Fred - book %d' % i, 'author_ids': [fred.data['id']]})

        for i in range(2):
            books.create({'title': 'Harry and Fred - book %d' % i, 'author_ids': [harry.data['id'], fred.data['id']]})

        books.pull()
        firstbook = books[0].follow('full')
        self.assertEqual(firstbook['author_ids'][0].data, harry.data['id'])
        author = firstbook['author_ids'][0].follow('full')
        self.assertEqual(author.data, harry.data)

        books.pull()
        self.assertEqual(len(books.data), 9)
        
        harrys_books = harry.follow('books')
        self.assertEqual(len(harrys_books.data), 5)

        freds_books = fred.follow('books')
        self.assertEqual(len(freds_books.data), 6)


if __name__ == '__main__':
    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    unittest.main()
