
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


from xosresource import XOSResource
from core.models import User, ServiceInstanceAttribute, Service, ServiceInstanceLink
from services.onos.models import ONOSApp, ONOSService

class XOSONOSApp(XOSResource):
    provides = ["tosca.nodes.ONOSApp", "tosca.nodes.ONOSvBNGApp", "tosca.nodes.ONOSvOLTApp", "tosca.nodes.ONOSVTNApp", "tosca.nodes.ONOSvRouterApp"]
    xos_model = ONOSApp
    copyin_props = ["service_specific_id", "dependencies", "install_dependencies"]

    def get_xos_args(self, throw_exception=True):
        args = super(XOSONOSApp, self).get_xos_args()

        # provider_service is mandatory and must be the ONOS Service
        provider_name = self.get_requirement("tosca.relationships.TenantOfService", throw_exception=throw_exception)
        if provider_name:
            args["owner"] = self.get_xos_object(ONOSService, throw_exception=throw_exception, name=provider_name)

        return args

    def set_tenant_attr(self, obj, prop_name, value):
        value = self.try_intrinsic_function(value)
        if value:
            attrs = ServiceInstanceAttribute.objects.filter(service_instance=obj, name=prop_name)
            if attrs:
                attr = attrs[0]
                if attr.value != value:
                    self.info("updating attribute %s" % prop_name)
                    attr.value = value
                    attr.save()
            else:
                self.info("adding attribute %s" % prop_name)
                ta = ServiceInstanceAttribute(service_instance=obj, name=prop_name, value=value)
                ta.save()

    def postprocess(self, obj):
        props = self.nodetemplate.get_properties()
        for (k,d) in props.items():
            v = d.value
            if k.startswith("config_"):
                self.set_tenant_attr(obj, k, v)
            elif k.startswith("rest_") and (k!="rest_hostname") and (k!="rest_port"):
                self.set_tenant_attr(obj, k, v)
            elif k.startswith("component_config"):
                self.set_tenant_attr(obj, k, v)
            elif k == "autogenerate":
                self.set_tenant_attr(obj, k, v)

        # subscriber_service is optional and can be any service
        subscriber_name = self.get_requirement("tosca.relationships.UsedByService", throw_exception=False)
        if subscriber_name:
            sub_serv = self.get_xos_object(Service, throw_exception=True, name=subscriber_name)
            existing_links = ServiceInstanceLink.objects.filter(provider_service_instance_id = obj.id, subscriber_service_id = sub_serv.id)
            if not existing_links:
                link = ServiceInstanceLink(provider_service_instance = obj, subscriber_service = sub_serv)
                link.save()

    def can_delete(self, obj):
        return super(XOSONOSApp, self).can_delete(obj)
