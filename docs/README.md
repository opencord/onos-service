# ONOS Service

This service is intended to manage ONOSes.

It can:

- push global configuration to ONOS
- install applications
- push application specific configuration

## Models

This service is composed by two models:

- `ONOSService` responsible to hold urls and authentication informations  
- `ONOSApp` represents and ONOS application and track its dependencies (this extend the `ServiceInstance` model)

This service uses `ServiceAttributes` and `ServiceInstanceAttributes`
to hold the configuration details.

For more informations about the models, please refer to the
[xproto](https://github.com/opencord/onos-service/blob/master/xos/synchronizer/models/onos.xproto) definition

### Example TOSCA

This is an example TOSCA recipe you can use to install an application
and add some configuration to it:

```yaml
tosca_definitions_version: tosca_simple_yaml_1_0
imports:
  - custom_types/onosapp.yaml
  - custom_types/onosservice.yaml
  - custom_types/serviceinstanceattribute.yaml
description: Configures fabric switches and related ports
topology_template:
  node_templates:
    service#onos:
      type: tosca.nodes.ONOSService
      properties:
        name: onos
        must-exist: true


    # Local app
    dhcp:
      type: tosca.nodes.ONOSApp
      properties:
        name: dhcp
        app_id: org.onosproject.dhcp
      requirements:
        - owner:
            node: service#onos
            relationship: tosca.relationships.BelongsToOne

    # Remote app
    cord-config:
      type: tosca.nodes.ONOSApp
      properties:
        app_id: org.opencord.cord-config
        name: cord-config
        url: https://oss.sonatype.org/content/repositories/public/org/opencord/cord-config/1.4.0-SNAPSHOT/cord-config-1.4.0-20180604.071543-275.oar
        version: 1.4.0.SNAPSHOT
      requirements:
        - owner:
            node: service#onos
            relationship: tosca.relationships.BelongsToOne

    # CORD-Configuration
    cord-config-attr:
      type: tosca.nodes.ServiceInstanceAttribute
      properties:
        name: /onos/v1/network/configuration/apps/org.opencord.olt
        value: >
          {
            "kafka" : {
              "bootstrapServers" : "cord-kafka-kafka.default.svc.cluster.local:9092"
            }
          }
      requirements:
        - service_instance:
            node: cord-config
            relationship: tosca.relationships.BelongsToOne
```

## Synchronization workflow

### ONOSService

Anytime an `ONOSService` model is created/updated, the synchronizer checks
for the corresponding `ServiceAttribute`s and if any are found it pushes the configuration
to ONOS

### ONOSServiceInstance

Anytime an `ONOSServiceInstance` model is created/updated, the synchronizer checks
for the corresponding `ServiceInstanceAttribute`s and if any are found:

- checks for the application dependencies
- if they are not matched defer the synchronization
- if they are matched
- it pushes the configuration to ONOS
- it installs/activates the application in ONOS

> ONOS Applications can be activated (if they already present in the container),
> in that case you just need to provide the `app_id`, or they can be installed from a remote `.oar`,
> in which case you need to also provide an `url` and a `version`
 