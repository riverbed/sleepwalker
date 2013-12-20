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
from sleepwalker.exceptions import DataPullError

from sim_connection import SimConnection

logger = logging.getLogger(__name__)

TEST_PATH = os.path.abspath(os.path.dirname(__file__))

class BasicConnection(SimConnection):

    def __init__(self, test=None):
        SimConnection.__init__(self, test)
        self.add_collection('items', 'item')
        self.add_collection('categories', 'category')
    
        self._x = 5

    def x_links_get(self, link, method, uri, data, params, headers):
        return self._x

    def x_links_set(self, link, method, uri, data, params, headers):
        self._x = data
        return self._x

    def x_links_action(self, link, method, uri, data, params, headers):
        return 21

    def x_links_action2(self, link, method, uri, data, params, headers):
        return {'t1': 15, 't2': 'foo'}

    def button_links_press(self, link, method, uri, data, params, headers):
        return None

    def items_links_get(self, link, method, uri, data, params, headers):
        if params:
            result = []
            for (key,value) in self._collections['items'].iteritems():
                for p,pv in params.iteritems():
                    if p == 'category' and value['category'] != pv:
                        continue
                    if p == 'label' and value['label'] != pv:
                        continue
                    result.append(key)
                
            return result
        else:
            return self._collections['items'].keys()

    def categories_links_get(self, link, method, uri, data, params, headers):
        if params:
            result = []
            for (key,value) in self._collections['categories'].iteritems():
                for p,pv in params.iteritems():
                    if p == 'label' and value['label'] != pv:
                        continue
                    result.append(key)
                
            return result
        else:
            return self._collections['categories'].keys()

class BasicTest(unittest.TestCase):

    def setUp(self):
        self.service = Service()
        self.service.load_restschema(os.path.join(TEST_PATH, "basic_schema.yml"))
        self.service.connection = BasicConnection(self)
        self.service.connection.add_restschema(self.service.restschema)

    def test_x(self):
        x = self.service.bind('x')
        self.assertEqual(type(x), DataRep)

        x.data = 3
        x.push()
        self.assertEqual(x.data, 3)
        
        x.data = 0
        x.pull()
        self.assertEqual(x.data, 3)

        resp = x.execute('get')
        self.assertEqual(resp.data, 3)

        resp = x.execute('set', 9)
        self.assertEqual(resp.data, 9)
        
        resp = x.execute('action', 20)
        self.assertEqual(resp.data, 21)

        resp = x.execute('action2')
        self.assertEqual(resp.data, {'t1': 15, 't2': 'foo'})

    def test_follow_relation(self):
        categories = self.service.bind('categories')
        new_category = categories.create({'label': 'foo'})
        categories.pull()
        category = categories['0'].follow('category')
        # explicitly not calling category.pull() here!
        #category.pull()
        items = category.follow('items')
        self.assertEqual(0, len(items.data))

        
    def test_item(self):
        categories = self.service.bind('categories')
        cat_home = categories.create({'label': 'home'})
        cat_garden = categories.create({'label': 'garden'})

        items = self.service.bind('items')
        stapler = items.create({'label': 'stapler',
                                'price': 10.99,
                                'category' : cat_home.data['id']
                                })
        logger.debug("Create item %s: %s" % (stapler, stapler.data))
        self.assertEqual(stapler.uri, '/api/basic/1.0/items/%d' % stapler.data['id'])

        item_schema = self.service.lookup_resource('item')
        logger.info("Binding item schema id=%d" % stapler.data['id'])
        item = item_schema.bind(id=stapler.data['id'])
        logger.debug("Bound item: %s" % item)
        item.pull()
        self.assertEqual(item.data, {'id': stapler.data['id'], 'label': 'stapler', 'price': 10.99, 'category': cat_home.data['id']})

        items.pull()
        self.assertEqual(items.data, [1])

        items = self.service.bind('items')
        ruler = items.create({'label': 'ruleer',
                              'price': 3.99,
                              'category' : cat_home.data['id']
                              })
        self.assertEqual(ruler.data, {'id': ruler.data['id'], 'label': 'ruleer', 'price': 3.99, 'category': cat_home.data['id']})
        logger.debug("Create item %s: %s" % (ruler, ruler.data))
        self.assertEqual(ruler.uri, '/api/basic/1.0/items/%d' % ruler.data['id'])

        items.pull()
        self.assertEqual(items.data, [1, 2])

        item = item_schema.bind(id=2)
        self.assertEqual(item.data, {'id': ruler.data['id'], 'label': 'ruleer', 'price': 3.99, 'category': cat_home.data['id']})

        self.assertEqual(ruler.data, {'id': ruler.data['id'], 'label': 'ruleer', 'price': 3.99, 'category': cat_home.data['id']})
        item.data['label'] = 'ruler'
        self.assertEqual(ruler.data, {'id': ruler.data['id'], 'label': 'ruleer', 'price': 3.99, 'category': cat_home.data['id']})
        item.push()

        item.pull()
        self.assertEqual(item.data, {'id': ruler.data['id'], 'label': 'ruler', 'price': 3.99, 'category': cat_home.data['id']})

        ruler.pull()
        self.assertEqual(ruler.data, {'id': ruler.data['id'], 'label': 'ruler', 'price': 3.99, 'category': cat_home.data['id']})

        rake = items.create({'label': 'rake',
                             'price': 24.99,
                             'category' : cat_garden.data['id']
                             })
        shovel = items.create({'label': 'shovel',
                               'price': 29.99,
                               'category' : cat_garden.data['id']
                               })
        lawn_mower = items.create({'label': 'lawn mower',
                                   'price': 129.99,
                                   'category' : cat_garden.data['id']
                                   })

        items.pull()
        self.assertEqual(len(items.data), 5)

        # Retreive all 'home' items via bind()
        home_items = self.service.bind('items', category=cat_home.data['id'])
        home_items.pull()
        logger.debug("home_items: %s => %s" % (home_items, home_items.data))
        self.assertEqual(len(home_items.data), 2)
        for elem in home_items:
            item = elem.follow('item')
            self.assertEqual(elem.follow('item').data['category'], cat_home.data['id'])

        # Retreive all 'garden' items via bind()
        garden_items = self.service.bind('items', category=cat_garden.data['id'])
        garden_items.pull()
        logger.debug("garden_items: %s => %s" % (garden_items, garden_items.data))
        self.assertEqual(len(garden_items.data), 3)
        for elems in garden_items:
            self.assertEqual(elems.follow('item').data['category'], cat_garden.data['id'])

        # Retreive all 'home' items via category.links.items
        home_items = cat_home.follow('items')
        home_items.pull()
        logger.debug("home_items: %s => %s" % (home_items, home_items.data))
        self.assertEqual(len(home_items.data), 2)
        for elems in home_items:
            self.assertEqual(elems.follow('item').data['category'], cat_home.data['id'])

        rulers= self.service.bind('items', label='ruler')
        ruler = rulers[0].follow('item')
        self.assertEqual(ruler['label'].data, 'ruler')
        ruler_label = ruler['label']
        ruler_label.data = 'metric ruler'
        ruler_label.push()

        ruler.data = None
        ruler.pull()
        self.assertEqual(ruler.data['label'], 'metric ruler')

        ruler.delete()
        rulers= self.service.bind('items', label='ruler')
        self.assertEqual(len(rulers.data), 0)
        
    def test_resolve_without_get(self):
        b = self.service.bind('button')
        result = b.execute('press', data={'pressure': 1})
        x = b.follow('x')
        self.assertEqual(x.uri, self.service.bind('x').uri)
        self.assertEqual(result.data, None)
        self.assertEqual(b._data, DataRep.UNSET)

    def test_resolve_after_invalid(self):
        cat = self.service.bind('category', id=1)
        cat._data = DataRep.FAIL
        self.assertRaises(DataPullError, cat.follow, 'items')
        self.assertRaises(DataPullError, cat.execute, 'purchase')
        
if __name__ == '__main__':
    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    unittest.main()
