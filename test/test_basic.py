# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

import os
import logging
import unittest
import re
import copy

from sleepwalker.datarep import DataRep
from sleepwalker.exceptions import DataPullError

from sim_server import SimServer, BadPassword
from service_loader import \
    ServiceDefLoader, SERVICE_MANAGER, TEST_SERVER_MANAGER


logger = logging.getLogger(__name__)

TEST_PATH = os.path.abspath(os.path.dirname(__file__))

ServiceDefLoader.register_servicedef(
    'http://support.riverbed.com/apis/basic/1.0',
    os.path.join(TEST_PATH, "service_basic.yml"))


class BasicServer(SimServer):

    def __init__(self, *args, **kwargs):
        SimServer.__init__(self, *args, **kwargs)
        self.add_collection('items', 'item')
        self.add_collection('categories', 'category')
        self.add_collection('nullints', 'nullint')

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

    def y_links_action(self, link, method, uri, data, params, headers):
        self._x = data
        return self._x

    def button_links_press(self, link, method, uri, data, params, headers):
        return None

    def item_links_extended(self, link, method, uri, data, params, headers):
        m = re.search('items/([^/]+)/extended', uri)
        item_id = int(m.group(1))
        extended_item = self._collections['items'][item_id]
        cat_id = int(extended_item['category'])
        extended_item['full_category'] = self._collections['categories'][cat_id]
        return extended_item

    def fullitems_links_get(self, link, method, uri, data, params, headers):
        return self._collections['items'].values()

    def fullitems_with_full_links_get(self, link, method, uri, data,
                                      params, headers):
        return self._collections['items'].values()

    def items_links_get(self, link, method, uri, data, params, headers):
        logger.debug("items_links_get ---------------------:\n%s" %
                     str(self._collections['items']))
        if params:
            result = []
            for (key, value) in self._collections['items'].iteritems():
                for p, pv in params.iteritems():
                    if p == 'category' and value['category'] != int(pv):
                        continue
                    if p == 'label' and value['label'] != pv:
                        continue
                    if p == 'min_price' and value['price'] < float(pv):
                        continue
                    result.append(key)

            return result
        else:
            return self._collections['items'].keys()

    def categories_links_get(self, link, method, uri, data, params, headers):
        if params:
            result = []
            for (key, value) in self._collections['categories'].iteritems():
                for p, pv in params.iteritems():
                    if p == 'label' and value['label'] != pv:
                        continue
                    result.append(key)

            return result
        else:
            return self._collections['categories'].keys()


class BasicTest(unittest.TestCase):

    def setUp(self):
        self.id = 'http://support.riverbed.com/apis/basic/1.0'
        self.host = 'http://basic-server:80'
        TEST_SERVER_MANAGER.reset()
        self.server = TEST_SERVER_MANAGER.register_server(
            self.host, self.id, None, BasicServer, self)

        self.service = SERVICE_MANAGER.find_by_id(self.host, self.id)

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

    def test_y(self):
        y = self.service.bind('y')
        self.assertEqual(type(y), DataRep)

        resp = y.execute('action', 20)
        self.assertEqual(resp.data, 20)

    def test_follow_relation(self):
        categories = self.service.bind('categories')
        categories.create({'label': 'foo'})
        categories.pull()
        category = categories[0].full()
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
                                'category': cat_home.data['id']})
        logger.debug("Create item %s: %s" % (stapler, stapler.data))
        self.assertEqual(stapler.uri, ('/api/basic/1.0/items/%d' %
                                       stapler.data['id']))

        item_schema = self.service.lookup_resource('item')
        logger.info("Binding item schema id=%d" % stapler.data['id'])
        item = item_schema.bind(id=stapler.data['id'])
        logger.debug("Bound item: %s" % item)
        item.pull()
        self.assertEqual(item.data, {'id': stapler.data['id'],
                                     'label': 'stapler',
                                     'price': 10.99,
                                     'category': cat_home.data['id']})

        items.pull()
        self.assertEqual(items.data, [1])

        items = self.service.bind('items')
        ruler = items.create({'label': 'ruleer',
                              'price': 3.99,
                              'category': cat_home.data['id']})
        self.assertEqual(ruler.data, {'id': ruler.data['id'],
                                      'label': 'ruleer',
                                      'price': 3.99,
                                      'category': cat_home.data['id']})
        logger.debug("Create item %s: %s" % (ruler, ruler.data))
        self.assertEqual(ruler.uri, ('/api/basic/1.0/items/%d' %
                                     ruler.data['id']))

        items.pull()
        self.assertEqual(items.data, [1, 2])

        item = item_schema.bind(id=2)
        self.assertEqual(item.data, {'id': ruler.data['id'],
                                     'label': 'ruleer',
                                     'price': 3.99,
                                     'category': cat_home.data['id']})

        self.assertEqual(ruler.data, {'id': ruler.data['id'],
                                      'label': 'ruleer',
                                      'price': 3.99,
                                      'category': cat_home.data['id']})
        item.data['label'] = 'ruler'
        self.assertEqual(ruler.data, {'id': ruler.data['id'],
                                      'label': 'ruleer',
                                      'price': 3.99,
                                      'category': cat_home.data['id']})
        item.push()

        item.pull()
        self.assertEqual(item.data, {'id': ruler.data['id'],
                                     'label': 'ruler',
                                     'price': 3.99,
                                     'category': cat_home.data['id']})

        ruler.pull()
        self.assertEqual(ruler.data, {'id': ruler.data['id'],
                                      'label': 'ruler',
                                      'price': 3.99,
                                      'category': cat_home.data['id']})

        items.create({'label': 'rake',
                      'price': 24.99,
                      'category': cat_garden.data['id']})

        items.create({'label': 'shovel',
                      'price': 29.99,
                      'category': cat_garden.data['id']})

        items.create({'label': 'lawn mower',
                      'price': 129.99,
                      'category': cat_garden.data['id']})

        items.pull()
        self.assertEqual(len(items.data), 5)

        # Retreive all 'home' items via bind()
        home_items = self.service.bind('items', category=cat_home.data['id'])
        home_items.pull()
        logger.debug("home_items: %s => %s" % (home_items, home_items.data))
        self.assertEqual(len(home_items.data), 2)
        for elem in home_items:
            item = elem.full()
            self.assertEqual(item.data['category'],
                             cat_home.data['id'])

        # Retreive all 'garden' items via bind()
        garden_items = self.service.bind('items',
                                         category=cat_garden.data['id'])
        garden_items.pull()
        logger.debug("garden_items: %s => %s" % (garden_items,
                                                 garden_items.data))
        self.assertEqual(len(garden_items.data), 3)
        for elem in garden_items:
            self.assertEqual(elem.full().data['category'],
                             cat_garden.data['id'])

        # Retreive all 'home' items via category.links.items
        home_items = cat_home.follow('items')
        home_items.pull()
        logger.debug("home_items: %s => %s" % (home_items, home_items.data))
        self.assertEqual(len(home_items.data), 2)
        for elem in home_items:
            item_data = copy.copy(elem.full().data)
            self.assertEqual(item_data['category'],
                             cat_home.data['id'])
            extended = elem.full().execute('extended')
            item_data['full_category'] = cat_home.data
            self.assertEqual(extended.data, item_data)

        rulers = self.service.bind('items', label='ruler')
        ruler = rulers[0].full()
        self.assertEqual(ruler['label'].data, 'ruler')
        ruler_label = ruler['label']
        ruler_label.data = 'metric ruler'
        ruler_label.push()

        ruler.data = None
        ruler.pull()
        self.assertEqual(ruler.data['label'], 'metric ruler')

        ruler.delete()
        rulers = self.service.bind('items', label='ruler')
        self.assertEqual(len(rulers.data), 0)

        # Check via 'fullitems' which is an array of $ref : item
        for name in ['fullitems', 'fullitems_with_full']:
            fullitems = self.service.bind(name)
            for i, item in enumerate(fullitems):
                # item is still a fragement of the fullitems collection
                self.assertEqual(item.uri, '/api/basic/1.0/%s' % name)
                self.assertEqual(item.fragment, '/%d' % i)

                # This 'full()' is resolved via the self link
                fullitem = item.full()

                # The fullitem should now be a normal item
                self.assertEqual(fullitem.uri, '/api/basic/1.0/items/%d' %
                                 item.data['id'])
                self.assertEqual(fullitem.fragment, '')
                self.assertEqual(fullitem.data, item.data)

    def test_resolve_without_get(self):
        b = self.service.bind('button')
        result = b.execute('press', {'pressure': 1})
        x = b.follow('x')
        self.assertEqual(x.uri, self.service.bind('x').uri)
        self.assertEqual(result.data, None)
        self.assertEqual(b._data, DataRep.UNSET)

    def test_resolve_after_invalid(self):
        cat = self.service.bind('category', id=1)
        cat._data = DataRep.FAIL
        self.assertRaises(DataPullError, cat.follow, 'items')
        self.assertRaises(DataPullError, cat.execute, 'purchase')


class BasicAuthTest(unittest.TestCase):

    class Auth(object):
        def __init__(self, username, password):
            self.username = username
            self.password = password

        def __call__(self, req):
            req.headers['auth_header'] = (self.username, self.password)

    def setUp(self):
        self.id = 'http://support.riverbed.com/apis/basic/1.0'
        self.host = 'http://basic-server:80'
        TEST_SERVER_MANAGER.reset()
        self.server = TEST_SERVER_MANAGER.register_server(
            self.host, self.id, None, BasicServer, self)
        self.server.allowed_auth = {'test': 'password'}

    def test_auth(self):
        service = SERVICE_MANAGER.find_by_id(
            self.host, self.id, auth=BasicAuthTest.Auth('test', 'password'))
        x = service.bind('x')
        x.data = 3
        x.push()

    def test_bad_password(self):
        service = SERVICE_MANAGER.find_by_id(
            self.host, self.id, auth=BasicAuthTest.Auth('test', 'badpassword'))
        x = service.bind('x')
        x.data = 3
        with self.assertRaises(BadPassword):
            x.push()


if __name__ == '__main__':
    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    unittest.main()
