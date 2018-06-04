# Copyright 2017-present Open Networking Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

import functools
from mock import patch, call, Mock, PropertyMock
import requests_mock
import multistructlog
from multistructlog import create_logger

import os, sys

# Hack to load synchronizer framework
test_path=os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
xos_dir=os.path.join(test_path, "../../..")
if not os.path.exists(os.path.join(test_path, "new_base")):
    xos_dir=os.path.join(test_path, "../../../../../../orchestration/xos/xos")
    services_dir = os.path.join(xos_dir, "../../xos_services")
sys.path.append(xos_dir)
sys.path.append(os.path.join(xos_dir, 'synchronizers', 'new_base'))
# END Hack to load synchronizer framework

# generate model from xproto
def get_models_fn(service_name, xproto_name):
    name = os.path.join(service_name, "xos", xproto_name)
    if os.path.exists(os.path.join(services_dir, name)):
        return name
    else:
        name = os.path.join(service_name, "xos", "synchronizer", "models", xproto_name)
        if os.path.exists(os.path.join(services_dir, name)):
            return name
    raise Exception("Unable to find service=%s xproto=%s" % (service_name, xproto_name))
# END generate model from xproto

def match_none(req):
    return req.text == None

def match_json(desired, req):
    if desired!=req.json():
        raise Exception("Got request %s, but body is not matching" % req.url)
        return False
    return True

class TestSyncOnosApp(unittest.TestCase):

    def setUp(self):
        global DeferredException

        self.sys_path_save = sys.path
        sys.path.append(xos_dir)
        sys.path.append(os.path.join(xos_dir, 'synchronizers', 'new_base'))

        # Setting up the config module
        from xosconfig import Config
        config = os.path.join(test_path, "../test_config.yaml")
        Config.clear()
        Config.init(config, "synchronizer-config-schema.yaml")
        # END Setting up the config module

        from synchronizers.new_base.mock_modelaccessor_build import build_mock_modelaccessor
        build_mock_modelaccessor(xos_dir, services_dir, [
            get_models_fn("onos-service", "onos.xproto")
        ])
        import synchronizers.new_base.modelaccessor

        from sync_onos_app import SyncONOSApp, DeferredException, model_accessor

        # import all class names to globals
        for (k, v) in model_accessor.all_model_classes.items():
            globals()[k] = v


        self.sync_step = SyncONOSApp

        onos = ONOSService()
        onos.rest_hostname = "onos-url"
        onos.rest_port = "8181"
        onos.rest_username = "karaf"
        onos.rest_password = "karaf"

        self.o = Mock()
        self.o.name = "vrouter"
        self.o.app_id = "org.onosproject.vrouter"
        self.o.dependencies = ""
        self.o.owner.leaf_model = onos
        self.o.serviceinstanceattribute_dict = {}
        self.o.url = None

    def tearDown(self):
        self.onos = None
        sys.path = self.sys_path_save

    @requests_mock.Mocker()
    def test_defer_app_sync(self, m):
        self.o.dependencies = "org.onosproject.segmentrouting, org.onosproject.openflow"

        segment_routing = Mock()
        segment_routing.app_id = "org.onosproject.segmentrouting"
        segment_routing.backend_code = 1

        openflow = Mock()
        openflow.app_id = "org.onosproject.openflow"
        openflow.backend_code = 0

        with patch.object(ONOSApp.objects, "get_items") as app_get, \
            self.assertRaises(DeferredException) as e:

            app_get.return_value = [segment_routing, openflow]
            self.sync_step().sync_record(self.o)

        self.assertEqual(e.exception.message, 'Deferring installation of "org.onosproject.vrouter" as dependencies are not met')
        self.assertFalse(m.called)

    @requests_mock.Mocker()
    def test_app_sync_local_app_no_config(self, m):
        """
        Activate an application that is already installed in ONOS
        """

        m.post("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter/active",
               status_code=200,
               additional_matcher=match_none)

        self.sync_step().sync_record(self.o)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 1)

    @requests_mock.Mocker()
    def test_app_sync_local_app_with_config(self, m):
        expected_conf = {'foo': 'bar'}

        self.o.serviceinstanceattribute_dict = {
            '/onos/v1/network/configuration/apps/org.onosproject.vrouter': expected_conf,
        }

        m.post("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter/active",
               status_code=200,
               additional_matcher=match_none)

        m.post("http://onos-url:8181/onos/v1/network/configuration/apps/org.onosproject.vrouter",
               status_code=200,
               additional_matcher=functools.partial(match_json, expected_conf))

        self.sync_step().sync_record(self.o)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 2)

    @requests_mock.Mocker()
    def test_app_sync_remote_app_no_config(self, m):
        """
        Activate an application that has to be downloaded from a remote source
        """

        self.o.url = 'http://onf.org/maven/...'

        expected = {
            'activate': True,
            'url': self.o.url
        }

        m.post("/onos/v1/applications",
               status_code=200,
               additional_matcher=functools.partial(match_json, expected))

        self.sync_step().sync_record(self.o)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 1)