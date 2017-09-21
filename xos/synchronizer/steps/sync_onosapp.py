
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


import hashlib
import os
import socket
import sys
import base64
import time
import re
import json
from collections import OrderedDict
from xosconfig import Config
from synchronizers.new_base.syncstep import DeferredException
from synchronizers.new_base.ansible_helper import run_template
from synchronizers.new_base.SyncInstanceUsingAnsible import SyncInstanceUsingAnsible
from synchronizers.new_base.modelaccessor import *
from xos.logger import Logger, logging

logger = Logger(level=logging.INFO)


class SyncONOSApp(SyncInstanceUsingAnsible):
    provides=[ONOSApp]
    observes=ONOSApp
    requested_interval=0
    template_name = "sync_onosapp.yaml"

    def __init__(self, *args, **kwargs):
        super(SyncONOSApp, self).__init__(*args, **kwargs)

    def get_instance(self, o):
        # We assume the ONOS service owns a slice, so pick one of the instances
        # inside that slice to sync to.

        serv = self.get_onos_service(o)

        if serv.no_container:
            raise Exception("get_instance() was called on a service that was marked no_container")

        if serv.slices.exists():
            slice = serv.slices.all()[0]
            if slice.instances.exists():
                return slice.instances.all()[0]

        return None

    def get_onos_service(self, o):
        if not o.owner:
            return None

        onoses = ONOSService.objects.filter(id=o.owner.id)
        if not onoses:
            return None

        return onoses[0]

    def is_no_container(self, o):
        return self.get_onos_service(o).no_container

    def skip_ansible_fields(self, o):
        return self.is_no_container(o)

    def get_files_dir(self, o):
        step_dir = Config.get("steps_dir")

        return os.path.join(step_dir, "..", "files", str(self.get_onos_service(o).id), o.name)

    def get_cluster_configuration(self, o):
        instance = self.get_instance(o)
        if not instance:
           raise Exception("No instance for ONOS App")
        node_ips = [socket.gethostbyname(instance.node.name)]

        ipPrefix = ".".join(node_ips[0].split(".")[:3]) + ".*"
        result = '{ "nodes": ['
        result = result + ",".join(['{ "ip": "%s"}' % ip for ip in node_ips])
        result = result + '], "ipPrefix": "%s"}' % ipPrefix
        return result

    def get_dynamic_parameter_value(self, o, param):
        instance = self.get_instance(o)
        if not instance:
           raise Exception("No instance for ONOS App")
        if param == 'rabbit_host':
            return instance.controller.rabbit_host
        if param == 'rabbit_user':
            return instance.controller.rabbit_user
        if param == 'rabbit_password':
            return instance.controller.rabbit_password
        if param == 'keystone_tenant_id':
            cslice = ControllerSlice.objects.get(slice=instance.slice)
            if not cslice:
                raise Exception("Controller slice object for %s does not exist" % instance.slice.name)
            return cslice.tenant_id
        if param == 'keystone_user_id':
            cuser = ControllerUser.objects.get(user=instance.creator)
            if not cuser:
                raise Exception("Controller user object for %s does not exist" % instance.creator)
            return cuser.kuser_id

    def write_configs(self, o):
        if hasattr(o, "create_attr"):
            # new API doesn't let us setattr for things that don't already exist
            o.create_attr("config_fns")
            o.create_attr("rest_configs")
            o.create_attr("component_configs")
            o.create_attr("files_dir")
            o.create_attr("node_key_fn")
            o.create_attr("early_rest_configs")

        o.config_fns = []
        o.rest_configs = []
        o.component_configs = []
        o.files_dir = self.get_files_dir(o)

        if not os.path.exists(o.files_dir):
            os.makedirs(o.files_dir)

        # Combine the service attributes with the tenant attributes. Tenant
        # attribute can override service attributes.
        attrs = o.owner.serviceattribute_dict
        attrs.update(o.tenantattribute_dict)

        # Check to see if we're waiting on autoconfig
        if (attrs.get("autogenerate") in ["vtn-network-cfg",]) and \
           (not attrs.get("rest_onos/v1/network/configuration/")):
            raise DeferredException("Network configuration is not populated yet")

        ordered_attrs = attrs.keys()

        onos = self.get_onos_service(o)
        if onos.node_key:
            file(os.path.join(o.files_dir, "node_key"),"w").write(onos.node_key)
            o.node_key_fn="node_key"
        else:
            o.node_key_fn=None

        o.early_rest_configs=[]
        if ("cordvtn" in o.dependencies) and (not self.is_no_container(o)):
            # For VTN, since it's running in a docker host container, we need
            # to make sure it configures the cluster using the right ip addresses.
            # NOTE: rest_onos/v1/cluster/configuration/ will reboot the cluster and
            #   must go first.
            name="rest_onos/v1/cluster/configuration/"
            value= self.get_cluster_configuration(o)
            fn = name[5:].replace("/","_")
            endpoint = name[5:]
            file(os.path.join(o.files_dir, fn),"w").write(" " +value)
            o.early_rest_configs.append( {"endpoint": endpoint, "fn": fn} )

        for name in attrs.keys():
            value = attrs[name]
            if name.startswith("config_"):
                fn = name[7:] # .replace("_json",".json")
                o.config_fns.append(fn)
                file(os.path.join(o.files_dir, fn),"w").write(value)
            if name.startswith("rest_"):
                fn = name[5:].replace("/","_")
                endpoint = name[5:]
                # Ansible goes out of it's way to make our life difficult. If
                # 'lookup' sees a file that it thinks contains json, then it'll
                # insist on parsing and return a json object. We just want
                # a string, so prepend a space and then strip the space off
                # later.
                file(os.path.join(o.files_dir, fn),"w").write(" " +value)
                o.rest_configs.append( {"endpoint": endpoint, "fn": fn} )
            if name.startswith("component_config"):
                components = json.loads(value,object_pairs_hook=OrderedDict)
                for component in components.keys():
                    config = components[component]
                    for key in config.keys():
                         config_val = config[key]
                         found = re.findall('<(.+?)>',config_val)
                         for x in found:
                            #Get value corresponding to that string
                            val = self.get_dynamic_parameter_value(o, x)
                            if val:
	                       config_val = re.sub('<'+x+'>', val, config_val)
                            #TODO: else raise an exception?
	                 o.component_configs.append( {"component": component, "config_params": "'{\""+key+"\":\""+config_val+"\"}'"} )

    def prepare_record(self, o):
        self.write_configs(o)

    def get_extra_attributes_common(self, o):
        fields = {}

        # These are attributes that are not dependent on Instance. For example,
        # REST API stuff.

        onos = self.get_onos_service(o)

        fields["files_dir"] = o.files_dir
        fields["appname"] = o.name
        fields["rest_configs"] = o.rest_configs
        fields["rest_hostname"] = onos.rest_hostname
        fields["rest_port"] = onos.rest_port

        if o.dependencies:
            fields["dependencies"] = [x.strip() for x in o.dependencies.split(",")]
        else:
            fields["dependencies"] = []

        if o.install_dependencies:
            fields["install_dependencies"] = [x.strip() for x in o.install_dependencies.split(",")]
        else:
            fields["install_dependencies"] = []

        return fields

    def get_extra_attributes_full(self, o):
        instance = self.get_instance(o)

        fields = self.get_extra_attributes_common(o)

        fields["config_fns"] = o.config_fns
        fields["early_rest_configs"] = o.early_rest_configs
        fields["component_configs"] = o.component_configs
        fields["node_key_fn"] = o.node_key_fn

        if (instance.isolation=="container"):
            fields["ONOS_container"] = "%s-%s" % (instance.slice.name, str(instance.id))
        else:
            fields["ONOS_container"] = "ONOS"
        return fields

    def get_extra_attributes(self, o):
        if self.is_no_container(o):
            return self.get_extra_attributes_common(o)
        else:
            return self.get_extra_attributes_full(o)

    def sync_fields(self, o, fields):
        # the super causes the playbook to be run
        super(SyncONOSApp, self).sync_fields(o, fields)

    def run_playbook(self, o, fields):
        if self.is_no_container(o):
            # There is no machine to SSH to, so use the synchronizer's
            # run_template method directly.
            run_template("sync_onosapp_nocontainer.yaml", fields, object=o)
        else:
            super(SyncONOSApp, self).run_playbook(o, fields)

    def delete_record(self, m):
        pass
