import hashlib
import os
import socket
import sys
import base64
import time
from xos.config import Config
from synchronizers.new_base.SyncInstanceUsingAnsible import SyncInstanceUsingAnsible
from synchronizers.new_base.modelaccessor import *
from xos.logger import Logger, logging

logger = Logger(level=logging.INFO)

class SyncONOSService(SyncInstanceUsingAnsible):
    provides=[ONOSService]
    observes=ONOSService
    requested_interval=0
    template_name = "sync_onosservice.yaml"

    def __init__(self, *args, **kwargs):
        super(SyncONOSService, self).__init__(*args, **kwargs)

    def get_instance(self, o):
        # We assume the ONOS service owns a slice, so pick one of the instances
        # inside that slice to sync to.

        serv = o

        if serv.slices.exists():
            slice = serv.slices.all()[0]
            if slice.instances.exists():
                return slice.instances.all()[0]

        return None

    def get_extra_attributes(self, o):
        fields={}
        fields["instance_hostname"] = self.get_instance(o).instance_name.replace("_","-")
        fields["appname"] = o.name
        fields["ONOS_container"] = "ONOS"
        return fields

    def sync_record(self, o):
        if o.no_container:
            logger.info("no work to do for onos service, because o.no_container is set",extra=o.tologdict())
            o.save()
        else:
            super(SyncONOSService, self).sync_record(o)

    def sync_fields(self, o, fields):
        # the super causes the playbook to be run
        super(SyncONOSService, self).sync_fields(o, fields)

    def run_playbook(self, o, fields):
        instance = self.get_instance(o)
        if (instance.isolation=="container"):
            # If the instance is already a container, then we don't need to
            # install ONOS.
            return
        super(SyncONOSService, self).run_playbook(o, fields)

    def delete_record(self, m):
        pass
