
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
from synchronizers.new_base.syncstep import SyncStep, DeferredException, model_accessor
from synchronizers.new_base.modelaccessor import ONOSApp, ServiceAttribute

from xosconfig import Config
from multistructlog import create_logger

from helpers import Helpers

log = create_logger(Config().get('logging'))


class SyncONOSApp(SyncStep):
    provides=[ONOSApp]
    observes=ONOSApp

    def check_app_dependencies(self, deps):
        """
        Check if all the dependencies required by this application are installed
        :param deps: comma separated list of application names
        :return: bool
        """
        print "\n", deps
        for dep in [x.strip() for x in deps.split(',') if x is not ""]:
            try:
                app = ONOSApp.objects.get(app_id=dep)
                if not app.backend_code == 1:
                    # backend_code == 1 means that the app has been pushed
                    return False
            except IndexError, e:
                print e
                return False
        return True

    def sync_record(self, o):

        if not self.check_app_dependencies(o.dependencies):
            raise DeferredException('Deferring installation of "%s" as dependencies are not met' % o.app_id)

        # getting onos url and auth
        onos_url = "%s:%s" % (Helpers.format_url(o.owner.leaf_model.rest_hostname), o.owner.leaf_model.rest_port)
        onos_basic_auth = HTTPBasicAuth(o.owner.leaf_model.rest_username, o.owner.leaf_model.rest_password)

        # push configs (if any)
        for url, value in o.serviceinstanceattribute_dict.iteritems():

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


        # install app (locally available)
        if not o.url or o.url is None:
            url = '%s/onos/v1/applications/%s/active' % (onos_url, o.app_id)
            request = requests.post(url, auth=onos_basic_auth)
        # install an app from a remote source
        else:
            data = {
                'activate': True,
                'url': o.url
            }
            url = '%s/onos/v1/applications' % onos_url
            request = requests.post(url, json=data, auth=onos_basic_auth)

        if request.status_code != 200:
            log.error("Request failed", response=request.text)
            raise Exception("Failed to add config %s in ONOS" % url)
        else:
            try:
                print request.json()
            except Exception:
                print request.text

    def delete_record(self, o):
        pass
