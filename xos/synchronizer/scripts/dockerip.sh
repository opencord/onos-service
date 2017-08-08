
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


#!/bin/bash

MODE=`docker inspect --format '{{ .HostConfig.NetworkMode }}' $1  | tr -d '\n' | tr -d '\r'`
if [[ "$MODE" == "host" ]]; then
    echo -n "127.0.0.1"
else
    docker inspect --format '{{ .NetworkSettings.IPAddress }}' $1 | tr -d '\n' | tr -d '\r'
fi

