
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


from xosapi.orm import register_convenience_wrapper
from xosapi.convenience.service import ORMWrapperService

class ORMWrapperOnosService(ORMWrapperService):

    """ Calling convention. Assume the subscribing service does approximately (needs some checks to see
        if the methods exist before calling them) the following in its model_policy:

        if not eastbound_service.validate_links(self):
             eastbound_service.acquire_service_instance(self)
    """

    def acquire_service_instance(self, subscriber_service_instance):
        """
        Never acquire a ServiceInstance on the ONOS Service,
        those are ONOS apps, simply return true
        """
        return True

    def validate_links(self, subscriber_service_instance):
        """
        In the case of the ONOS service there are no links between ServiceInstances and ONOSApps,
        so alway return an empty list
        """
        return []

register_convenience_wrapper("ONOSService", ORMWrapperOnosService)
