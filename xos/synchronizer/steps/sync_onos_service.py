
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
from xossynchronizer.steps.syncstep import SyncStep
from xossynchronizer.modelaccessor import ONOSService, Service, ServiceAttribute, model_accessor

from xosconfig import Config
from multistructlog import create_logger

from helpers import Helpers

log = create_logger(Config().get('logging'))

class SyncONOSService(SyncStep):
    provides = [ONOSService]
    observes = [ONOSService, ServiceAttribute]

    def get_service_attribute(self, o):
        # NOTE this method is defined in the core convenience methods for services
        svc = Service.objects.get(id=o.id)
        return svc.serviceattribute_dict

    def sync_record(self, o):
        if hasattr(o, 'service'):
            # this is a ServiceAttribute model
            if 'ONOSService' in o.service.leaf_model.class_names:
                print "sync ONOSService Attribute", o.service.leaf_model
                return self.sync_record(o.service.leaf_model)
            return # if it's not related to an ONOSService do nothing

        onos_url = "%s:%s" % (Helpers.format_url(o.rest_hostname), o.rest_port)
        onos_basic_auth = HTTPBasicAuth(o.rest_username, o.rest_password)

        configs = self.get_service_attribute(o)
        for url, value in configs.iteritems():

            if url[0] == "/":
                # strip initial /
                url = url[1:]

            url = '%s/%s' % (onos_url, url)
            value = json.loads(value)
            request = requests.post(url, json=value, auth=onos_basic_auth)

            if request.status_code != 200:
                log.error("Request failed", response=request.text)
                raise Exception("Failed to add config %s in ONOS" % url)

    def delete_record(self, o):

        if hasattr(o, 'service'):
            # this is a ServiceAttribute model
            if 'ONOSService' in o.service.leaf_model.class_names:
                print "sync ONOSService Attribute", o.service.leaf_model

                log.info("Deleting config %s" % o.name)
                # getting onos url and auth
                onos_service = o.service.leaf_model
                onos_url = "%s:%s" % (
                Helpers.format_url(onos_service.rest_hostname), onos_service.rest_port)
                onos_basic_auth = HTTPBasicAuth(onos_service.rest_username,
                                                onos_service.rest_password)

                url = o.name
                if url[0] == "/":
                    # strip initial /
                    url = url[1:]

                url = '%s/%s' % (onos_url, url)
                request = requests.delete(url, auth=onos_basic_auth)

                if request.status_code != 204:
                    log.error("Request failed", response=request.text)
                    raise Exception("Failed to remove config %s from ONOS:  %s" % (url, request.text))
