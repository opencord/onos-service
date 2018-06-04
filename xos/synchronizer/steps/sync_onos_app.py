
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

import json
import requests
from requests.auth import HTTPBasicAuth
from synchronizers.new_base.syncstep import SyncStep, DeferredException, model_accessor
from synchronizers.new_base.modelaccessor import ONOSApp, ServiceInstance, ServiceInstanceAttribute

from xosconfig import Config
from multistructlog import create_logger

from helpers import Helpers

log = create_logger(Config().get('logging'))
log.info("config file", file=Config().get_config_file())

class SyncONOSApp(SyncStep):
    provides=[ONOSApp]
    observes=[ONOSApp, ServiceInstanceAttribute]

    def get_service_instance_attribute(self, o):
        # NOTE this method is defined in the core convenience methods for service_instances
        svc = ServiceInstance.objects.get(id=o.id)
        return svc.serviceinstanceattribute_dict

    def check_app_dependencies(self, deps):
        """
        Check if all the dependencies required by this application are installed
        :param deps: comma separated list of application names
        :return: bool
        """
        for dep in [x.strip() for x in str(deps).split(',') if x is not ""]:
            try:
                app = ONOSApp.objects.get(app_id=dep)
                if not app.backend_code == 1:
                    # backend_code == 1 means that the app has been pushed
                    return False
            except IndexError, e:
                return False
        return True

    def push_config(self, o, onos_url, onos_basic_auth):
        # push configs (if any)
        configs = self.get_service_instance_attribute(o)
        for url, value in configs.iteritems():

            if url[0] == "/":
                # strip initial /
                url = url[1:]

            url = '%s/%s' % (onos_url, url)
            value = json.loads(value)
            request = requests.post(url, json=value, auth=onos_basic_auth)

            if request.status_code != 200:
                log.error("Request failed", response=request.text)
                raise Exception("Failed to add config %s in ONOS:  %s" % (url, request.text))
            else:
                try:
                    print request.json()
                except Exception:
                    print request.text

    def activate_app(self, o, onos_url, onos_basic_auth):
        url = '%s/onos/v1/applications/%s/active' % (onos_url, o.app_id)
        request = requests.post(url, auth=onos_basic_auth)

        if request.status_code != 200:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to add application %s to ONOS: %s" % (url, request.text))
        else:
            try:
                print request.json()
            except Exception:
                print request.text

        url = '%s/onos/v1/applications/%s' % (onos_url, o.app_id)
        request = requests.get(url, auth=onos_basic_auth)

        if request.status_code != 200:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to read application %s from ONOS: %s" % (url, request.text))
        else:
            o.version = request.json()["version"]

    def install_app(self, o, onos_url, onos_basic_auth):

        # TODO what will happen if I install two times the same app?

        if not o.version or o.version is None:
            # TODO move this validation in the model.py (if the url is there version must there and app_id must not)
            raise Exception('You need to specify a version')
        data = {
            'activate': True,
            'url': o.url
        }
        url = '%s/onos/v1/applications' % onos_url
        request = requests.post(url, json=data, auth=onos_basic_auth)

        if request.status_code != 200:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to add application %s to ONOS: %s" % (url, request.text))
        else:
            try:
                print request.json()
            except Exception:
                print request.text

        url = '%s/onos/v1/applications/%s' % (onos_url, o.app_id)
        request = requests.get(url, auth=onos_basic_auth)

        if request.status_code != 200:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to read application %s from ONOS: %s" % (url, request.text))
        else:
            o.app_id = request.json()["name"]
            if o.version != request.json()["version"]:
                raise Exception("The version of %s you installed (%s) is not the same you requested (%s)" % (o.app_id, request.json()["version"], o.version))

    def sync_record(self, o):

        if hasattr(o, 'service_instance'):
            # this is a ServiceInstanceAttribute model
            if 'ONOSApp' in o.service_instance.leaf_model.class_names:
                return self.sync_record(o.service_instance.leaf_model)
            return # if it's not an ONOSApp do nothing

        if not self.check_app_dependencies(o.dependencies):
            raise DeferredException('Deferring installation of "%s" as dependencies are not met' % o.app_id)

        # getting onos url and auth
        onos_url = "%s:%s" % (Helpers.format_url(o.owner.leaf_model.rest_hostname), o.owner.leaf_model.rest_port)
        onos_basic_auth = HTTPBasicAuth(o.owner.leaf_model.rest_username, o.owner.leaf_model.rest_password)

        self.push_config(o, onos_url, onos_basic_auth)

        # install app (locally available), only if it as not been installed before
        if not o.url or o.url is None and o.backend_code != 1:
            self.activate_app(o, onos_url, onos_basic_auth)
        # install an app from a remote source
        if o.url and o.url is not None:
            self.install_app(o, onos_url, onos_basic_auth)

    def delete_record(self, o):
        pass
