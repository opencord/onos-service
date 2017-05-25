def __init__(self, *args, **kwargs):
    onos_services = ONOSService.objects.all()
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

