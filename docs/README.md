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

This service uses `ServiceAttributes` and `ServiceInstanceAttributes` to hold the configuration details

For more informations about the models, please refer to the [xproto](https://github.com/opencord/onos-service/blob/master/xos/synchronizer/models/onos.xproto) definition 