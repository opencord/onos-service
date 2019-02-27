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


class TestKubernetesEvent(unittest.TestCase):

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

        from kubernetes_event import KubernetesPodDetailsEventStep

        from xossynchronizer.modelaccessor import model_accessor

        self.model_accessor = model_accessor

        from mock_modelaccessor import MockObjectList

        from kubernetes_event import KubernetesPodDetailsEventStep

        # import all class names to globals
        for (k, v) in model_accessor.all_model_classes.items():
            globals()[k] = v

        self.event_step = KubernetesPodDetailsEventStep

        self.onos = ONOSService(name="myonos",
                                rest_hostname = "onos-url",
                                rest_port = "8181",
                                rest_username = "karaf",
                                rest_password = "karaf",
                                backend_code=1,
                                backend_status="succeeded")

        self.attr = ServiceInstanceAttribute(
            name="foo",
            value="bar"
        )

        self.mockAllAttr = Mock()
        self.mockAllAttr.all.return_value = [self.attr]

        self.app1 = ONOSApp(name="myapp1",
                           owner=self.onos,
                           backend_code=1,
                           backend_status="succeeded",
                           service_instance_attributes=self.mockAllAttr)

        self.app2 = ONOSApp(name="myapp2",
                           owner=self.onos,
                           backend_code=1,
                           backend_status="succeeded",
                           service_instance_attributes=self.mockAllAttr)

        self.onos.service_instances = MockObjectList([self.app1, self.app2])

        self.log = Mock()

    def tearDown(self):
        self.onos = None
        sys.path = self.sys_path_save

    def test_process_event(self):
        with patch.object(ONOSService.objects, "get_items") as service_objects, \
             patch.object(ONOSService, "save", autospec=True) as service_save, \
             patch.object(ONOSApp, "save", autospec=True) as app_save, \
             patch.object(ServiceInstanceAttribute, "save", autospec=True) as attr_save:
            service_objects.return_value = [self.onos]

            event_dict = {"status": "created",
                          "labels": {"xos_service": "myonos"}}
            event = Mock()
            event.value = json.dumps(event_dict)

            step = self.event_step(log=self.log, model_accessor=self.model_accessor)
            step.process_event(event)

            self.assertEqual(self.onos.backend_code, 0)
            self.assertEqual(self.onos.backend_status, "resynchronize due to kubernetes event")
            service_save.assert_called_with(self=self.onos, update_fields=["updated", "backend_code", "backend_status"],
                                            always_update_timestamp=True)

            self.assertEqual(self.app1.backend_code, 0)
            self.assertEqual(self.app1.backend_status, "resynchronize due to kubernetes event")

            self.assertEqual(self.app2.backend_code, 0)
            self.assertEqual(self.app2.backend_status, "resynchronize due to kubernetes event")
            app_save.assert_has_calls([call(self.app1, update_fields=["updated", "backend_code", "backend_status"],
                                            always_update_timestamp=True),
                                       call(self.app2, update_fields=["updated", "backend_code", "backend_status"],
                                            always_update_timestamp=True)])

            self.assertEqual(self.attr.backend_code, 0)
            self.assertEqual(self.attr.backend_status, "resynchronize due to kubernetes event")
            self.assertEqual(attr_save.call_count, 2)

    def test_process_event_unknownstatus(self):
        with patch.object(ONOSService.objects, "get_items") as service_objects, \
                patch.object(ONOSService, "save") as service_save, \
                patch.object(ONOSApp, "save") as app_save:
            service_objects.return_value = [self.onos]

            event_dict = {"status": "something_else",
                          "labels": {"xos_service": "myonos"}}
            event = Mock()
            event.value = json.dumps(event_dict)

            step = self.event_step(log=self.log, model_accessor=self.model_accessor)
            step.process_event(event)

            self.assertEqual(self.onos.backend_code, 1)
            self.assertEqual(self.onos.backend_status, "succeeded")
            service_save.assert_not_called()

            self.assertEqual(self.app1.backend_code, 1)
            self.assertEqual(self.app1.backend_status, "succeeded")
            app_save.assert_not_called()

            self.assertEqual(self.app2.backend_code, 1)
            self.assertEqual(self.app2.backend_status, "succeeded")

    def test_process_event_unknownservice(self):
        with patch.object(ONOSService.objects, "get_items") as service_objects, \
                patch.object(ONOSService, "save") as service_save, \
                patch.object(ONOSApp, "save") as app_save:
            service_objects.return_value = [self.onos]

            event_dict = {"status": "created",
                          "labels": {"xos_service": "some_other_service"}}
            event = Mock()
            event.value = json.dumps(event_dict)

            step = self.event_step(log=self.log, model_accessor=self.model_accessor)
            step.process_event(event)

            self.assertEqual(self.onos.backend_code, 1)
            self.assertEqual(self.onos.backend_status, "succeeded")
            service_save.assert_not_called()

            self.assertEqual(self.app1.backend_code, 1)
            self.assertEqual(self.app1.backend_status, "succeeded")
            app_save.assert_not_called()

            self.assertEqual(self.app2.backend_code, 1)
            self.assertEqual(self.app2.backend_status, "succeeded")

    def test_process_event_nolabels(self):
        with patch.object(ONOSService.objects, "get_items") as service_objects, \
                patch.object(ONOSService, "save") as service_save, \
                patch.object(ONOSApp, "save") as app_save:
            service_objects.return_value = [self.onos]

            event_dict = {"status": "created"}
            event = Mock()
            event.value = json.dumps(event_dict)

            step = self.event_step(log=self.log, model_accessor=self.model_accessor)
            step.process_event(event)

            self.assertEqual(self.onos.backend_code, 1)
            self.assertEqual(self.onos.backend_status, "succeeded")
            service_save.assert_not_called()

            self.assertEqual(self.app1.backend_code, 1)
            self.assertEqual(self.app1.backend_status, "succeeded")
            app_save.assert_not_called()

            self.assertEqual(self.app2.backend_code, 1)
            self.assertEqual(self.app2.backend_status, "succeeded")



if __name__ == '__main__':
    unittest.main()



