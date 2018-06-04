
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

import requests
from requests.auth import HTTPBasicAuth
from synchronizers.new_base.syncstep import SyncStep, model_accessor
from synchronizers.new_base.modelaccessor import ONOSService, ServiceAttribute

from xosconfig import Config
from multistructlog import create_logger

from helpers import Helpers

log = create_logger(Config().get('logging'))

class SyncONOSService(SyncStep):
    provides=[ONOSService]
    observes=ONOSService

    def get_service_attribute(self, o):
        # NOTE this method is defined in the core convenience methods for services
        return o.serviceattribute_dict

    def sync_record(self, o):
        onos_url = "%s:%s" % (Helpers.format_url(o.rest_hostname), o.rest_port)
        onos_basic_auth = HTTPBasicAuth(o.rest_username, o.rest_password)

        configs = self.get_service_attribute(o)
        for url, value in configs.iteritems():

            if url[0] == "/":
                # strip initial /
                url = url[1:]

            url = '%s/%s' % (onos_url, url)
            request = requests.post(url, json=value, auth=onos_basic_auth)

            if request.status_code != 200:
                log.error("Request failed", response=request.text)
                raise Exception("Failed to add config %s in ONOS" % url)
            else:
                try:
                    print request.json()
                except Exception:
                    print request.text

    def delete_record(self, m):
        pass
