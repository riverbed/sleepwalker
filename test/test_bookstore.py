# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

import os
import logging
import unittest

from sim_server import SimServer
from service_loader import \
    SERVICE_MANAGER, ServiceDefLoader, TEST_SERVER_MANAGER

logger = logging.getLogger(__name__)

TEST_PATH = os.path.abspath(os.path.dirname(__file__))

ServiceDefLoader.register_servicedef(
    'http://support.riverbed.com/apis/bookstore/1.0',
    os.path.join(TEST_PATH, "Bookstore.yml"))


class BookstoreServer(SimServer):
    def __init__(self, *args, **kwargs):
        SimServer.__init__(self, *args, **kwargs)
        self.add_collection('books', 'book')
        self.add_collection('authors', 'author')
        self.add_collection('publishers', 'publisher')

    def books_links_get(self, link, method, uri, data, params, headers):
        result = []
        for v in self._collections['books'].values():
            add = True
            if params:
                for p, pv in params.iteritems():
                    if p == 'author' and pv not in v['author_ids']:
                        add = False
                        break
            if add:
                result.append({'id': v['id'], 'title': v['title']})
        return result

    def book_links_purchase(self, link, method, uri, data, params, headers):
        response = {'delivery_date': 'Oct 1',
                    'final_cost': data['num_copies'] * 12.99}
        return response


class BookstoreTest(unittest.TestCase):
    def setUp(self):
        bookstore_id = 'http://support.riverbed.com/apis/bookstore/1.0'
        TEST_SERVER_MANAGER.reset()
        TEST_SERVER_MANAGER.register_server(
            'http://bookstore-server:80', bookstore_id, None,
            BookstoreServer, self)

        self.service = SERVICE_MANAGER.find_by_id('http://bookstore-server:80',
                                                  bookstore_id)

    def test_bookstore(self):
        authors = self.service.bind('authors')
        harry = authors.create({'name': 'Harry'})
        fred = authors.create({'name': 'Fred'})

        books = self.service.bind('books')
        for i in range(3):
            books.create({'title': 'Harry - book %d' % i,
                          'author_ids': [harry.data['id']]})

        for i in range(4):
            books.create({'title': 'Fred - book %d' % i,
                          'author_ids': [fred.data['id']]})

        for i in range(2):
            books.create({'title': 'Harry and Fred - book %d' % i,
                          'author_ids': [harry.data['id'], fred.data['id']]})

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
