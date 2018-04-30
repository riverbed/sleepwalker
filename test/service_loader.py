# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

import os
import logging
import re

from requests.structures import CaseInsensitiveDict

from reschema import ServiceDef, ServiceDefManager
from sleepwalker import ServiceManager, ConnectionManager

logger = logging.getLogger(__name__)

TEST_PATH = os.path.abspath(os.path.dirname(__file__))


class ServiceDefLoader(object):
    service_map = {}

    @classmethod
    def register_servicedef(cls, id, filename):
        cls.service_map[id] = filename

    def find_by_id(self, id_):
        if id_ in self.service_map:
            return ServiceDef.create_from_file(self.service_map[id_])
        else:
            raise KeyError("Invalid id: %s" % id_)

    def find_by_name(self, name, version, provider):
        assert(provider == 'riverbed')
        sid = ('http://support.riverbed.com/apis/%s/%s' %
               (name, version))
        return self.find_by_id(sid)


SERVICE_DEF_MANAGER = ServiceDefManager()
SERVICE_DEF_MANAGER.add_load_hook(ServiceDefLoader())

CONNECTION_MANAGER = ConnectionManager()
SERVICE_MANAGER = ServiceManager(servicedef_manager=SERVICE_DEF_MANAGER,
                                 connection_manager=CONNECTION_MANAGER)


class TestRequest(object):

    def __init__(self, conn, method, uri, data, params, headers):
        self.conn = conn
        self.method = method
        self.uri = uri
        self.data = data
        self.params = params
        self.headers = CaseInsensitiveDict(headers or {})


class TestConnection(object):

    def __init__(self, server_manager, host, auth):
        self.server_manager = server_manager
        self.host = host
        self.auth = auth

    def close(self):
        pass

    def json_request(self, method, uri, data, params, headers):
        logger.info("%s %s params=%s, data=%s" % (method, uri, params, data))
        for path, server in (iter(self.server_manager
                             .server_map[self.host].items())):
            logger.debug('Comparing path %s to uri %s' % (path, uri))

            if re.match("^%s(.*)$" % path, uri):
                req = TestRequest(self, method, uri, data, params, headers)
                if self.auth:
                    self.auth(req)
                return server.request(req)

        raise KeyError('Failed to find a server to handle uri: %s' % uri)


class TestServerManager(object):
    server_map = {}

    def __init__(self, service_manager):
        self.service_manager = service_manager

    @classmethod
    def register_server(cls, host, id, instance, servercls, test):
        service = SERVICE_MANAGER.find_by_id(host, id, instance)

        server = servercls(service, test)
        m = cls.server_map
        if host not in m:
            m[host] = {}
        m[host][service.servicepath] = server

        logger.info("Registered server: %s -> %s" % (service.servicepath,
                                                     servercls))
        return server

    def reset(self):
        logger.info("Resetting registered servers")
        TestServerManager.server_map = {}
        self.service_manager.connection_manager.reset()

    def connect(self, host, auth):
        return TestConnection(self, host, auth)

TEST_SERVER_MANAGER = TestServerManager(SERVICE_MANAGER)
CONNECTION_MANAGER.add_conn_hook(TEST_SERVER_MANAGER)
