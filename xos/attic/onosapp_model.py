def __init__(self, *args, **kwargs):
    onos_services = ONOSService.objects.all()
    if onos_services:
        self._meta.get_field("owner").default = onos_services[0].id
    super(ONOSApp, self).__init__(*args, **kwargs)

