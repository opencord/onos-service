from header import *



from core.models import User#from core.models.tenant import Tenant
from core.models import Tenant



#from core.models.service import Service
from core.models import Service





class ONOSApp(Tenant):

  KIND = "onos"

  class Meta:
      app_label = "onos"
      name = "onos"
      verbose_name = "ONOS Service"

  # Primitive Fields (Not Relations)
  install_dependencies = TextField( blank = True, null = True, db_index = False )
  dependencies = TextField( blank = True, null = True, db_index = False )
  

  # Relations
  
  creator = ForeignKey(User, db_index = True, related_name = 'onos_apps', null = True, blank = True )

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
  
  pass




class ONOSService(Service):

  KIND = "onos"

  class Meta:
      app_label = "onos"
      name = "onos"
      verbose_name = "ONOS Service"

  # Primitive Fields (Not Relations)
  rest_hostname = StrippedCharField( db_index = False, max_length = 255, null = True, blank = True )
  rest_port = IntegerField( default = 8181, null = False, blank = False, db_index = False )
  no_container = BooleanField( default = False, null = False, blank = True, db_index = False )
  node_key = StrippedCharField( db_index = False, max_length = 1024, null = True, blank = True )
  

  # Relations
  

  
  pass


