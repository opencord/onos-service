from django.db import models
from core.models import Service, PlCoreBase, Slice, Instance, Tenant, TenantWithContainer, Node, Image, User, Flavor, Subscriber
from core.models.plcorebase import StrippedCharField
import os
from django.db import models, transaction
from django.forms.models import model_to_dict
from django.db.models import Q
from operator import itemgetter, attrgetter, methodcaller
import traceback
from xos.exceptions import *
from core.models import SlicePrivilege, SitePrivilege
from sets import Set

ONOS_KIND = "onos"

class ONOSService(Service):
    KIND = ONOS_KIND

    class Meta:
        app_label = "onos"
        verbose_name = "ONOS Service"

    rest_hostname = StrippedCharField(max_length=255, null=True, blank=True)
    rest_port = models.IntegerField(default=8181)
    no_container = models.BooleanField(default=False)
    node_key = StrippedCharField(max_length=1024, null=True, blank=True)

class ONOSApp(Tenant):   # aka 'ONOSTenant'
    class Meta:
        app_label = "onos"

    KIND = ONOS_KIND

    name = StrippedCharField(max_length=255, null=True, blank=True)
    install_dependencies = models.TextField(null=True, blank=True)
    dependencies = models.TextField(null=True, blank=True)

    # why is this necessary?
    creator = models.ForeignKey(User, related_name='onos_apps', blank=True, null=True)

    def __init__(self, *args, **kwargs):
        onos_services = ONOSService.get_service_objects().all()
        if onos_services:
            self._meta.get_field("provider_service").default = onos_services[0].id
        super(ONOSApp, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creator:
            if not getattr(self, "caller", None):
                # caller must be set when creating a vCPE since it creates a slice
                raise XOSProgrammingError("ONOSApp's self.caller was not set")
            self.creator = self.caller
            if not self.creator:
                raise XOSProgrammingError("ONOSApp's self.creator was not set")

        super(ONOSApp, self).save(*args, **kwargs)




