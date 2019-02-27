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
from xossynchronizer.steps.syncstep import SyncStep, DeferredException
from xossynchronizer.modelaccessor import model_accessor
from xossynchronizer.modelaccessor import ONOSApp, ServiceInstance, ServiceInstanceAttribute

from xosconfig import Config
from multistructlog import create_logger

from helpers import Helpers

log = create_logger(Config().get('logging'))
log.info("config file", file=Config().get_config_file())

class SyncONOSApp(SyncStep):
    provides = [ONOSApp]
    observes = [ONOSApp, ServiceInstanceAttribute]

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
        if not deps:
            return True
        for dep in [x.strip() for x in deps.split(',') if x is not ""]:
            try:
                app = ONOSApp.objects.get(app_id=dep)
                if not app.backend_code == 1:
                    # backend_code == 1 means that the app has been pushed
                    return False
            except IndexError, e:
                return False
        return True

    def add_config(self, o):
        log.info("Adding config %s" % o.name, model=o.tologdict())
        # getting onos url and auth
        onos_url = "%s:%s" % (Helpers.format_url(o.service_instance.leaf_model.owner.leaf_model.rest_hostname), o.service_instance.leaf_model.owner.leaf_model.rest_port)
        onos_basic_auth = HTTPBasicAuth(o.service_instance.leaf_model.owner.leaf_model.rest_username, o.service_instance.leaf_model.owner.leaf_model.rest_password)

        # push configs (if any)
        url = o.name
        if url[0] == "/":
            # strip initial /
            url = url[1:]

        url = '%s/%s' % (onos_url, url)
        value = json.loads(o.value)
        request = requests.post(url, json=value, auth=onos_basic_auth)

        if request.status_code != 200:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to add config %s in ONOS:  %s" % (url, request.text))

    def activate_app(self, o, onos_url, onos_basic_auth):
        log.info("Activating app %s" % o.app_id)
        url = '%s/onos/v1/applications/%s/active' % (onos_url, o.app_id)
        request = requests.post(url, auth=onos_basic_auth)

        if request.status_code != 200:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to add application %s to ONOS: %s" % (url, request.text))

        url = '%s/onos/v1/applications/%s' % (onos_url, o.app_id)
        request = requests.get(url, auth=onos_basic_auth)

        if request.status_code != 200:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to read application %s from ONOS: %s" % (url, request.text))
        else:
            o.version = request.json()["version"]

    def check_app_installed(self, o, onos_url, onos_basic_auth):
        log.debug("Checking if app is installed", app=o.app_id)
        url = '%s/onos/v1/applications/%s' % (onos_url, o.app_id)
        request = requests.get(url, auth=onos_basic_auth)

        if request.status_code == 200:
            if "version" in request.json() and o.version == request.json()["version"]:
                log.debug("App is installed", app=o.app_id)
                return True
            else:
                # uninstall the application
                self.uninstall_app(o, onos_url, onos_basic_auth)
                return False
        if request.status_code == 404:
            # app is not installed at all
            return False
        else:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to read application %s from ONOS aaa: %s" % (url, request.text))

    def install_app(self, o, onos_url, onos_basic_auth):
        log.info("Installing app from url %s" % o.url, app=o.app_id, version=o.version)

        # check is the already installed app is the correct version
        is_installed = self.check_app_installed(o, onos_url, onos_basic_auth)

        if is_installed:
            # if the app is already installed we don't need to do anything
            log.info("App is installed, skipping install", app=o.app_id)
            return

        data = {
            'activate': True,
            'url': o.url
        }
        url = '%s/onos/v1/applications' % onos_url
        request = requests.post(url, json=data, auth=onos_basic_auth)

        if request.status_code == 409:
            log.info("App was already installed", app=o.app_id, test=request.text)
            return

        if request.status_code != 200:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to add application %s to ONOS: %s" % (url, request.text))

        log.debug("App from url %s installed" % o.url, app=o.app_id, version=o.version)

        url = '%s/onos/v1/applications/%s' % (onos_url, o.app_id)
        request = requests.get(url, auth=onos_basic_auth)

        if request.status_code != 200:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to read application %s from ONOS: %s while checking correct version" % (url, request.text))
        else:
            if o.version != request.json()["version"]:
                raise Exception("The version of %s you installed (%s) is not the same you requested (%s)" % (o.app_id, request.json()["version"], o.version))

    def sync_record(self, o):
        log.info("Sync'ing", model=o.tologdict())
        if hasattr(o, 'service_instance'):
            # this is a ServiceInstanceAttribute model just push the config
            if 'ONOSApp' in o.service_instance.leaf_model.class_names:
                return self.add_config(o)
            return # if it's not an ONOSApp do nothing

        if not self.check_app_dependencies(o.dependencies):
            raise DeferredException('Deferring installation of ONOSApp with id %s as dependencies are not met' % o.id)

        # getting onos url and auth
        onos_url = "%s:%s" % (Helpers.format_url(o.owner.leaf_model.rest_hostname), o.owner.leaf_model.rest_port)
        onos_basic_auth = HTTPBasicAuth(o.owner.leaf_model.rest_username, o.owner.leaf_model.rest_password)

        # activate app (bundled in onos)
        if not o.url or o.url is None:
            self.activate_app(o, onos_url, onos_basic_auth)
        # install an app from a remote source
        if o.url and o.url is not None:
            self.install_app(o, onos_url, onos_basic_auth)

    def delete_config(self, o):
        log.info("Deleting config %s" % o.name)
        # getting onos url and auth
        onos_app = o.service_instance.leaf_model
        onos_url = "%s:%s" % (Helpers.format_url(onos_app.owner.leaf_model.rest_hostname), onos_app.owner.leaf_model.rest_port)
        onos_basic_auth = HTTPBasicAuth(onos_app.owner.leaf_model.rest_username, onos_app.owner.leaf_model.rest_password)

        url = o.name
        if url[0] == "/":
            # strip initial /
            url = url[1:]

        url = '%s/%s' % (onos_url, url)
        request = requests.delete(url, auth=onos_basic_auth)

        if request.status_code != 204:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to remove config %s from ONOS:  %s" % (url, request.text))

    def uninstall_app(self,o, onos_url, onos_basic_auth):
        log.info("Uninstalling app %s" % o.app_id)
        url = '%s/onos/v1/applications/%s' % (onos_url, o.app_id)

        request = requests.delete(url, auth=onos_basic_auth)

        if request.status_code != 204:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to delete application %s from ONOS: %s" % (url, request.text))

    def deactivate_app(self, o, onos_url, onos_basic_auth):
        log.info("Deactivating app %s" % o.app_id)
        url = '%s/onos/v1/applications/%s/active' % (onos_url, o.app_id)

        request = requests.delete(url, auth=onos_basic_auth)

        if request.status_code != 204:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to deactivate application %s from ONOS: %s" % (url, request.text))

    def delete_record(self, o):

        if hasattr(o, 'service_instance'):
            # this is a ServiceInstanceAttribute model
            if 'ONOSApp' in o.service_instance.leaf_model.class_names:
                return self.delete_config(o)
            return # if it's not related to an ONOSApp do nothing

        # NOTE if it is an ONOSApp we don't care about the ServiceInstanceAttribute
        # as the reaper will delete it

        # getting onos url and auth
        onos_url = "%s:%s" % (Helpers.format_url(o.owner.leaf_model.rest_hostname), o.owner.leaf_model.rest_port)
        onos_basic_auth = HTTPBasicAuth(o.owner.leaf_model.rest_username, o.owner.leaf_model.rest_password)

        # deactivate an app (bundled in onos)
        if not o.url or o.url is None:
            self.deactivate_app(o, onos_url, onos_basic_auth)
        # uninstall an app from a remote source, only if it has been activated before
        if o.url and o.url is not None:
            self.uninstall_app(o, onos_url, onos_basic_auth)
