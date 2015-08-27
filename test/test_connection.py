# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

import os
import logging
import unittest
import urlparse

import mock
import requests.exceptions

import sleepwalker.exceptions

from sleepwalker.connection import Connection, URLError

logger = logging.getLogger(__name__)

HTTPBIN = (os.environ.get('HTTPBIN_URL', 'http://httpbin.org/')
           .rstrip('/') + '/')
HTTPSBIN = (os.environ.get('HTTPSBIN_URL', 'https://httpbin.org/')
            .rstrip('/') + '/')


def httpbin(*suffix):
    """Returns url for HTTPBIN resource."""
    return urlparse.urljoin(HTTPBIN, '/'.join(suffix))


class ConnectionTest(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_hostnames(self):
        conn = Connection(HTTPBIN)
        self.assertEqual(conn.hostname, HTTPBIN)

        conn = Connection(HTTPSBIN)
        self.assertEqual(conn.hostname, HTTPSBIN)

        conn = Connection('http://example.com')
        self.assertEqual(conn.hostname, 'http://example.com')

        conn = Connection('https://example.com')
        self.assertEqual(conn.hostname, 'https://example.com')

        conn = Connection('https://example.com', port='20483')
        self.assertEqual(conn.hostname, 'https://example.com:20483')

    def test_requests_connection_error(self):
        def side_effect(*args, **kwargs):
            raise requests.exceptions.ConnectionError(
                "ConnectionError from 'requests'")

        conn = Connection('https://example.com')
        conn._ssladapter = True
        conn.conn.request = mock.Mock(side_effect=side_effect)

        with self.assertRaises(sleepwalker.exceptions.ConnectionError):
            conn._request('GET', '/anything')

    def test_requests_ssl_error(self):
        def side_effect(*args, **kwargs):
            raise requests.exceptions.SSLError("SSLError from 'requests'")

        conn = Connection('https://example.com')
        conn._ssladapter = True
        conn.conn.request = mock.Mock(side_effect=side_effect)

        with self.assertRaises(sleepwalker.exceptions.ConnectionError):
            conn._request('GET', '/anything')

    def test_missing_schema(self):
        with self.assertRaises(URLError):
            Connection('example.com', port=666)

    def test_port_mismatch(self):
        with self.assertRaises(URLError):
            Connection('http://example.com:20483', port=666)

    def test_json_request(self):
        conn = Connection(HTTPBIN)
        r = conn.json_request('GET', httpbin('get'))
        self.assertEqual(r['headers']['Accept'], 'application/json')
        self.assertEqual(r['headers']['Content-Type'], 'application/json')
        self.assertEqual(conn.response.status_code, 200)

    def test_404(self):
        conn = Connection(HTTPBIN)
        with self.assertRaises(sleepwalker.exceptions.HTTPNotFound):
            try:
                conn.json_request('GET', httpbin('get/notfound'))
            except sleepwalker.exceptions.HTTPNotFound as hnf:
                self.assertEqual(hnf.http_code, 404)
                raise


if __name__ == '__main__':
    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    unittest.main()
