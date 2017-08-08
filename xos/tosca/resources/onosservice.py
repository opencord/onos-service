
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


from service import XOSService
from core.models import ServiceAttribute
from services.onos.models import ONOSService

class XOSONOSService(XOSService):
    provides = "tosca.nodes.ONOSService"
    xos_model = ONOSService
    copyin_props = ["view_url", "icon_url", "enabled", "published", "public_key", "versionNumber", "rest_hostname", "rest_port", "no_container", "node_key"]

    def set_service_attr(self, obj, prop_name, value):
        value = self.try_intrinsic_function(value)
        if value:
            attrs = ServiceAttribute.objects.filter(service=obj, name=prop_name)
            if attrs:
                attr = attrs[0]
                if attr.value != value:
                    self.info("updating attribute %s" % prop_name)
                    attr.value = value
                    attr.save()
            else:
                self.info("adding attribute %s" % prop_name)
                ta = ServiceAttribute(service=obj, name=prop_name, value=value)
                ta.save()

    def postprocess(self, obj):
        props = self.nodetemplate.get_properties()
        for (k,d) in props.items():
            v = d.value
            if k.startswith("config_"):
                self.set_service_attr(obj, k, v)
            elif k.startswith("rest_")  and (k!="rest_hostname") and (k!="rest_port"):
                self.set_service_attr(obj, k, v)

