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
import json
import functools
from mock import patch, call, Mock, PropertyMock
import requests_mock

import os, sys

test_path=os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


def match_json(desired, req):
    if desired!=req.json():
        raise Exception("Got request %s, but body is not matching" % req.url)
        return False
    return True

class TestSyncOnosService(unittest.TestCase):

    def setUp(self):

        self.sys_path_save = sys.path

        # Setting up the config module
        from xosconfig import Config
        config = os.path.join(test_path, "../test_config.yaml")
        Config.clear()
        Config.init(config, "synchronizer-config-schema.yaml")
        # END Setting up the config module

        from xossynchronizer.mock_modelaccessor_build import mock_modelaccessor_config
        mock_modelaccessor_config(test_path, [("onos-service", "onos.xproto"),])

        import xossynchronizer.modelaccessor
        import mock_modelaccessor
        reload(mock_modelaccessor) # in case nose2 loaded it in a previous test
        reload(xossynchronizer.modelaccessor)      # in case nose2 loaded it in a previous test

        from sync_onos_service import SyncONOSService, model_accessor

        self.model_accessor = model_accessor

        # import all class names to globals
        for (k, v) in model_accessor.all_model_classes.items():
            globals()[k] = v


        self.sync_step = SyncONOSService

        self.onos = Mock(spec=[
            'id',
            'name',
            "rest_hostname",
            "rest_port",
            "rest_username",
            "rest_password",
            "class_names"
        ])
        self.onos.id = 1
        self.onos.name = "onos"
        self.onos.rest_hostname = "onos-url"
        self.onos.rest_port = "8181"
        self.onos.rest_username = "karaf"
        self.onos.rest_password = "karaf"
        self.onos.class_names = "ONOSService"

        self.service = Mock()
        self.service.id = 1
        self.service.serviceattribute_dict = {}
        self.service.leaf_model = self.onos

        self.onos_service_attribute = Mock(spec=[
            'id',
            'service',
            'name',
            'value'
        ])
        self.onos_service_attribute.service = self.service
        self.onos_service_attribute.name = "/onos/v1/network/configuration/apps/org.opencord.olt"
        self.onos_service_attribute.value = {
            "kafka": {
                "bootstrapServers": "cord-kafka-kafka.default.svc.cluster.local:9092"
            }
        }

    def tearDown(self):
        self.onos = None
        sys.path = self.sys_path_save

    @requests_mock.Mocker()
    def test_sync_no_service_attributes(self, m):
        with patch.object(Service.objects, "get_items") as service_mock:
            service_mock.return_value = [self.service]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos)
        self.assertFalse(m.called)

    @requests_mock.Mocker()
    def test_sync_service_attributes_from_service(self, m):
        expected_conf = '{"foo": "bar"}'

        self.service.serviceattribute_dict = {
            '/onos/v1/network/configuration/apps/org.onosproject.olt': expected_conf,
            '/onos/v1/network/configuration/apps/org.onosproject.dhcp': expected_conf
        }

        m.post("http://onos-url:8181/onos/v1/network/configuration/apps/org.onosproject.olt",
               status_code=200,
               additional_matcher=functools.partial(match_json, json.loads(expected_conf)))

        m.post("http://onos-url:8181/onos/v1/network/configuration/apps/org.onosproject.dhcp",
               status_code=200,
               additional_matcher=functools.partial(match_json, json.loads(expected_conf)))

        with patch.object(Service.objects, "get_items") as service_mock:
            service_mock.return_value = [self.service]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 2)

    @requests_mock.Mocker()
    def test_sync_service_attributes_from_attribute(self, m):
        expected_conf = '{"foo": "bar"}'
        self.service.serviceattribute_dict = {
            '/onos/v1/network/configuration/apps/org.onosproject.olt': expected_conf,
        }
        m.post("http://onos-url:8181/onos/v1/network/configuration/apps/org.onosproject.olt",
               status_code=200,
               additional_matcher=functools.partial(match_json, json.loads(expected_conf)))

        with patch.object(Service.objects, "get_items") as service_mock:
            service_mock.return_value = [self.service]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos_service_attribute)

        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 1)

    @requests_mock.Mocker()
    def test_sync_service_attributes_err(self, m):
        expected_conf = '{"foo": "bar"}'

        self.service.serviceattribute_dict = {
            '/onos/v1/network/configuration/apps/org.onosproject.olt': expected_conf,
        }

        m.post("http://onos-url:8181/onos/v1/network/configuration/apps/org.onosproject.olt",
               status_code=500,
               text="Mock Error",
               additional_matcher=functools.partial(match_json, json.loads(expected_conf)))

        with self.assertRaises(Exception) as e, \
            patch.object(Service.objects, "get_items") as service_mock:

            service_mock.return_value = [self.service]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos)

        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 1)
        self.assertEqual(e.exception.message, "Failed to add config http://onos-url:8181/onos/v1/network/configuration/apps/org.onosproject.olt in ONOS")

    @requests_mock.Mocker()
    def test_delete(self, m):
        m.delete("http://onos-url:8181%s" % self.onos_service_attribute.name,
                 status_code=204)

        self.sync_step(model_accessor=self.model_accessor).delete_record(self.onos_service_attribute)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 1)

if __name__ == '__main__':
    unittest.main()
