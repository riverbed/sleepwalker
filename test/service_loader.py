import os
from reschema import ServiceDef, ServiceDefCache

TEST_PATH = os.path.abspath(os.path.dirname(__file__))


class Hook(object):
    service_map = {
        'http://support.riverbed.com/apis/basic/1.0':
        os.path.join(TEST_PATH, "service_basic.yml"),

        'http://support.riverbed.com/apis/catalog/1.0':
        os.path.join(TEST_PATH, "Catalog.yml")
        }

    def find_by_id(self, id_):
        if id_ in self.service_map:
            s = ServiceDef()
            s.load(self.service_map[id_])
            return s
        else:
            raise KeyError("Invalid id: %s" % id_)

    def find_by_name(self, name, version, provider):
        assert(provider == 'riverbed')
        sid = ('http://support.riverbed.com/apis/%s/%s' %
               (name, version))
        return self.find_by_id(sid)


SERVICE_DEF_CACHE = ServiceDefCache()
SERVICE_DEF_CACHE.add_load_hook(Hook())
