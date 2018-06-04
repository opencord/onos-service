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
> in which case you just need to provide an `url` 
 