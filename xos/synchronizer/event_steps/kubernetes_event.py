
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
import os
import sys
from synchronizers.new_base.eventstep import EventStep
from synchronizers.new_base.modelaccessor import ONOSApp, ONOSService
from xosconfig import Config
from multistructlog import create_logger

log = create_logger(Config().get('logging'))

class SimpleExampleEventStep(EventStep):
    topics = ["xos.kubernetes.pod-details"]
    technology = "kafka"

    def __init__(self, *args, **kwargs):
        super(SimpleExampleEventStep, self).__init__(*args, **kwargs)

    def process_event(self, event):
        value = json.loads(event.value)

        if (value.get("status") != "created"):
            return

        if "labels" not in value:
            return

        xos_service = value["labels"].get("xos_service")
        if not xos_service:
            return

        for service in ONOSService.objects.filter(name = xos_service):
            log.info("Dirtying ONOS Service", service=service)
            service.save(update_fields=["updated"], always_update_timestamp=True)

            for app in service.service_instances.all():
                log.info("Dirtying ONOS App", app=app)
                app.save(update_fields=["updated"], always_update_timestamp=True)
