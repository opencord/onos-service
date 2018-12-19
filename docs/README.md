# ONOS Service

This service manages ONOS and apps contained within ONOS. Although at this time CORD typically uses only one deployment of ONOS on a pod, this service is capable of managing multiple deployments of ONOS.

The ONOS Service is responsible for:

- Pushing global configuration to ONOS.
- Installing and activating applications.
- Pushing application specific configuration.
- Deactivating and uninstalling applications.

## Models

This service is composed of two models:

- `ONOSService`. Contains global service parameters. In addition to standard `Service` fields such as the `name` of the service, this model contains the following ONOS specific fields:
    - `rest_hostname`. Hostname of ONOS rest API endpoint.
    - `rest_port`. Port of ONOS rest endpoint.
    - `rest_username`. Username to use when authenticating to ONOS.
    - `rest_password`. Password to use when authenticating to ONOS.
- `ONOSApp` represents an ONOS application and tracks its dependencies. This model extends the `ServiceInstance` model, adding the following fields:
    - `app_id`. Application identifier.
    - `dependencies`. Comma-separated list of apps that must be installed before this app.
    - `url`. URL at which the application is available, if it needs to be downloaded.
    - `version`. Version of the app.

In addition to the above models, this service uses `ServiceAttributes` and
`ServiceInstanceAttributes` to hold additional configuration details for the
ONOSService and ONOSApp models.

For more information about the models, please refer to the
[xproto](https://github.com/opencord/onos-service/blob/master/xos/synchronizer/models/onos.xproto) definition

## Example TOSCA

The following TOSCA recipe is a subset of a recipe taken from the seba-services profile that configures ONOS services as for the 6.1 release of CORD. For the complete recipe, please see the SEBA profile.

```tosca_definitions_version: tosca_simple_yaml_1_0

imports:
   - custom_types/onosapp.yaml
   - custom_types/onosservice.yaml
   - custom_types/serviceinstanceattribute.yaml

description: Configures the VOLTHA ONOS service

topology_template:
  node_templates:

    service#onos:
      type: tosca.nodes.ONOSService
      properties:
          name: onos
          kind: data
          rest_hostname: "onos-ui.default.svc.cluster.local"
          rest_port: 8181

    onos_app#olt:
      type: tosca.nodes.ONOSApp
      properties:
        name: olt
        app_id: org.opencord.olt
        url: https://oss.sonatype.org/service/local/repositories/releases/content/org/opencord/olt-app/2.1.0/olt-app-2.1.0.oar
        version: 2.1.0
        dependencies: org.opencord.sadis
      requirements:
        - owner:
            node: service#onos
            relationship: tosca.relationships.BelongsToOne

    onos_app#sadis:
      type: tosca.nodes.ONOSApp
      properties:
        name: sadis
        app_id: org.opencord.sadis
        url: https://oss.sonatype.org/service/local/repositories/releases/content/org/opencord/sadis-app/2.2.0/sadis-app-2.2.0.oar
        version: 2.2.0
      requirements:
        - owner:
            node: service#onos
            relationship: tosca.relationships.BelongsToOne

    olt-config-attr:
      type: tosca.nodes.ServiceInstanceAttribute
      properties:
        name: /onos/v1/configuration/org.opencord.olt.impl.Olt?preset=true
        value: >
          {
            "enableDhcpOnProvisioning" : true
          }
      requirements:
        - service_instance:
            node: onos_app#olt
            relationship: tosca.relationships.BelongsToOne

    sadis-config-attr:
      type: tosca.nodes.ServiceInstanceAttribute
      properties:
        name: /onos/v1/network/configuration/apps/org.opencord.sadis
        value: >
          {
            "sadis" : {
              "integration" : {
                "cache" : {
                  "maxsize" : 1000,
                  "ttl": "PT300S"
                },
                "url" : "http://sadis-service:8000/subscriber/%s"
              }
            }
          }
      requirements:
        - service_instance:
            node: onos_app#sadis
            relationship: tosca.relationships.BelongsToOne
```

## Integration with other Services

The ONOS service is a dependency of many other services, including the Fabric and Fabric-crosconnect services. The ONOS service often is responsible for bringing up and configuring apps that these other services use.

## Synchronization workflow

### ONOSService

Any time an `ONOSService` model is created/updated, the synchronizer checks
for the corresponding `ServiceAttributes` and if any are found it pushes the configuration to ONOS.

### ONOSServiceInstance

Any time an `ONOSServiceInstance` model is created/updated, the synchronizer checks
for the corresponding `ServiceInstanceAttributes` and if any are found:

- checks for the application dependencies
- if they are not matched
    - defer the synchronization
- if they are matched
    - it pushes the configuration to ONOS
    - it installs/activates the application in ONOS

> ONOS Applications can be activated if they already present in the container
> by providing the `app_id`. If an application is not already present in the
> container then it can be installed from a remote `.oar`,
> in which case it is necessary to also provide an `url` and a `version`
