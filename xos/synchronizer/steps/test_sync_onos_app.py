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

        from sync_onos_app import SyncONOSApp, DeferredException, model_accessor

        self.model_accessor = model_accessor

        # import all class names to globals
        for (k, v) in model_accessor.all_model_classes.items():
            globals()[k] = v


        self.sync_step = SyncONOSApp

        onos = ONOSService()
        onos.rest_hostname = "onos-url"
        onos.rest_port = "8181"
        onos.rest_username = "karaf"
        onos.rest_password = "karaf"

        self.onos_app = Mock(spec=[
            'id',
            'name',
            'app_id',
            'dependencies',
            'owner',
            'url',
            'backend_code',
            'version',
            'tologdict'
        ])
        self.onos_app.id = 1
        self.onos_app.name = "vrouter"
        self.onos_app.app_id = "org.onosproject.vrouter"
        self.onos_app.dependencies = ""
        self.onos_app.owner.leaf_model = onos
        self.onos_app.url = None
        self.onos_app.class_names = "ONOSApp"
        self.onos_app.tologdict.return_value = ""

        self.si = Mock()
        self.si.id = 1
        self.si.leaf_model = self.onos_app

        self.vrouter_app_response = {
            "name": "org.onosproject.vrouter",
            "version": "1.13.1",
        }

        self.onos_app_attribute = Mock(spec=[
            'id',
            'service_instance',
            'name',
            'value'
        ])
        self.onos_app_attribute.id = 1
        self.onos_app_attribute.service_instance = self.si
        self.onos_app_attribute.name = "/onos/v1/network/configuration/apps/org.opencord.olt"
        self.onos_app_attribute.value = {
            "kafka" : {
                "bootstrapServers" : "cord-kafka-kafka.default.svc.cluster.local:9092"
            }
        }

    def tearDown(self):
        self.onos = None
        sys.path = self.sys_path_save

    @requests_mock.Mocker()
    def test_defer_app_sync(self, m):
        self.onos_app.dependencies = "org.onosproject.segmentrouting, org.onosproject.openflow"

        segment_routing = Mock()
        segment_routing.app_id = "org.onosproject.segmentrouting"
        segment_routing.backend_code = 1

        openflow = Mock()
        openflow.app_id = "org.onosproject.openflow"
        openflow.backend_code = 0

        with patch.object(ONOSApp.objects, "get_items") as app_get, \
            patch.object(ServiceInstance.objects, "get_items") as mock_si, \
            self.assertRaises(DeferredException) as e:

            app_get.return_value = [segment_routing, openflow]
            mock_si.return_value = [self.si]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos_app)

        self.assertEqual(e.exception.message, 'Deferring installation of ONOSApp with id 1 as dependencies are not met')
        self.assertFalse(m.called)

    @requests_mock.Mocker()
    def test_dependencies_none(self, m):
        """ App should sync if dependencies is set to None """

        self.onos_app.dependencies = None

        m.post("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter/active",
               status_code=200,
               additional_matcher=match_none)

        m.get("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter",
               status_code=200,
               json=self.vrouter_app_response)

        self.si.serviceinstanceattribute_dict = {}

        with patch.object(ServiceInstance.objects, "get_items") as mock_si:
            mock_si.return_value = [self.si]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos_app)

        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 2)
        self.assertEqual(self.onos_app.version, self.vrouter_app_response["version"])

    @requests_mock.Mocker()
    def test_app_sync_local_app_no_config(self, m):
        """
        Activate an application that is already installed in ONOS
        """

        m.post("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter/active",
               status_code=200,
               additional_matcher=match_none)

        m.get("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter",
               status_code=200,
               json=self.vrouter_app_response)

        self.si.serviceinstanceattribute_dict = {}

        with patch.object(ServiceInstance.objects, "get_items") as mock_si:
            mock_si.return_value = [self.si]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos_app)

        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 2)
        self.assertEqual(self.onos_app.version, self.vrouter_app_response["version"])

    @requests_mock.Mocker()
    def test_app_sync_local_app_with_config(self, m):

        m.post("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter/active",
               status_code=200,
               additional_matcher=match_none)

        m.get("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter",
              status_code=200,
              json=self.vrouter_app_response)

        with patch.object(ServiceInstance.objects, "get_items") as mock_si:
            mock_si.return_value = [self.si]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos_app)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 2)
        self.assertEqual(self.onos_app.version, self.vrouter_app_response["version"])

    @requests_mock.Mocker()
    def test_app_install_remote_app_no_config(self, m):
        """
        Install an application that has to be downloaded from a remote source
        """

        self.onos_app.url = 'http://onf.org/maven/...'
        self.onos_app.version = "1.13.1"
        self.onos_app.app_id = "org.onosproject.vrouter"

        expected = {
            'activate': True,
            'url': self.onos_app.url
        }

        m.post("/onos/v1/applications",
               status_code=200,
               additional_matcher=functools.partial(match_json, expected),
               json=self.vrouter_app_response)

        m.get("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter", [
            {'status_code': 404, 'text': "foo"},
            {'status_code': 200, 'json': self.vrouter_app_response}
        ])

        self.si.serviceinstanceattribute_dict = {}

        with patch.object(ServiceInstance.objects, "get_items") as mock_si:
            mock_si.return_value = [self.si]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos_app)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 3)
        self.assertEqual(self.onos_app.app_id, self.vrouter_app_response["name"])

    @requests_mock.Mocker()
    def test_update_remote_app(self, m):
        self.onos_app.url = 'http://onf.org/maven/...'
        self.onos_app.version = "1.14.1"

        expected = {
            'activate': True,
            'url': self.onos_app.url
        }

        self.vrouter_app_response_updated = self.vrouter_app_response.copy()
        self.vrouter_app_response_updated["version"] = "1.14.1"

        m.post("/onos/v1/applications",
               status_code=200,
               additional_matcher=functools.partial(match_json, expected),
               json=self.vrouter_app_response)


        m.get("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter",
              [
                  {"json": self.vrouter_app_response, "status_code": 200},
                  {"json": self.vrouter_app_response_updated, "status_code": 200}
              ]
        )

        m.delete("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter",
                 status_code=204)

        self.si.serviceinstanceattribute_dict = {}

        with patch.object(ServiceInstance.objects, "get_items") as mock_si:
            mock_si.return_value = [self.si]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos_app)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 4)
        self.assertEqual(self.onos_app.app_id, self.vrouter_app_response_updated["name"])

    @requests_mock.Mocker()
    def test_app_sync_remote_app_no_config_fail_version(self, m):
        """
        Activate an application that has to be downloaded from a remote source
        """

        self.onos_app.url = 'http://onf.org/maven/...'
        self.onos_app.version = "1.14.2"
        self.onos_app.app_id = "org.onosproject.vrouter"

        expected = {
            'activate': True,
            'url': self.onos_app.url
        }

        m.post("/onos/v1/applications",
               status_code=200,
               additional_matcher=functools.partial(match_json, expected),
               json=self.vrouter_app_response)

        m.get("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter", [
            {'status_code': 404, 'text': "foo"},
            {'status_code': 200, 'json': self.vrouter_app_response}
        ])

        self.si.serviceinstanceattribute_dict = {}

        with patch.object(ServiceInstance.objects, "get_items") as mock_si, \
            self.assertRaises(Exception) as e:
            mock_si.return_value = [self.si]
            self.sync_step(model_accessor=self.model_accessor).sync_record(self.onos_app)

        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 3)
        self.assertEqual(self.onos_app.app_id, self.vrouter_app_response["name"])
        self.assertEqual(e.exception.message, "The version of org.onosproject.vrouter you installed (1.13.1) is not the same you requested (1.14.2)")

    @requests_mock.Mocker()
    def test_handle_409(self, m):
        """
        A 409 "Application Already installed" response is not an error. This should not happen as we check if the app is installed.
        """

        self.onos_app.url = 'http://onf.org/maven/...'
        self.onos_app.version = "1.14.2"
        self.onos_app.app_id = "org.onosproject.vrouter"

        m.post("/onos/v1/applications",
               status_code=409)

        step = self.sync_step(model_accessor=self.model_accessor)
        with patch.object(step, "check_app_installed") as mock_check_installed:
            mock_check_installed.return_value = False

            step.sync_record(self.onos_app)

        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 1)

    @requests_mock.Mocker()
    def test_config_delete(self, m):
        m.delete("http://onos-url:8181%s" % self.onos_app_attribute.name,
               status_code=204)

        self.sync_step(model_accessor=self.model_accessor).delete_record(self.onos_app_attribute)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 1)

    @requests_mock.Mocker()
    def test_app_deactivate(self, m):
        m.delete("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter/active",
               status_code=204)

        self.sync_step(model_accessor=self.model_accessor).delete_record(self.onos_app)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 1)

    @requests_mock.Mocker()
    def test_app_uninstall(self, m):
        self.onos_app.url = 'http://onf.org/maven/...'
        self.onos_app.version = "1.14.2"
        self.onos_app.backend_code = 1

        m.delete("http://onos-url:8181/onos/v1/applications/org.onosproject.vrouter",
                 status_code=204)

        self.sync_step(model_accessor=self.model_accessor).delete_record(self.onos_app)
        self.assertTrue(m.called)
        self.assertEqual(m.call_count, 1)

if __name__ == '__main__':
    unittest.main()

