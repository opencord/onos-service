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

from xos.exceptions import XOSValidationError

from models_decl import ONOSApp_decl
from models_decl import ONOSService_decl

class ONOSApp(ONOSApp_decl):
    class Meta:
        proxy = True

    def save(self, *args, **kwargs):

        if self.url and not self.version:
            raise XOSValidationError("If you specify a url, you also need to specify a version. ONOSApp:  %s" % self.name)

        super(ONOSApp, self).save(*args, **kwargs)


class ONOSService(ONOSService_decl):
   class Meta:
        proxy = True 

