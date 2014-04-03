import os
import logging

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


class TestServerManager(object):
    server_map = {}

    def __init__(self, service_manager):
        self.service_manager = service_manager

    @classmethod
    def register_server(cls, server, conncls, test):
        logger.info("Registered server: %s -> %s" % (server, conncls))
        cls.server_map[server] = (conncls, test)

    def reset(self):
        logger.info("Resetting registered servers")
        TestServerManager.server_map = {}
        self.service_manager.connection_manager.reset()

    def connect(self, host):
        (conncls, test) = TestServerManager.server_map[host]
        return conncls(test, self.service_manager)

TEST_SERVER_MANAGER = TestServerManager(SERVICE_MANAGER)
CONNECTION_MANAGER.add_conn_hook(TEST_SERVER_MANAGER)
