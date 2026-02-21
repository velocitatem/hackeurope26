# OpenShift Local (CRC) Setup

This folder contains manifests and commands to run a local OpenShift simulation and submit a simple NYC Taxi dummy ML workload.

## 1) Install prerequisites

- OpenShift Local (`crc`)
- OpenShift CLI (`oc`)
- A Red Hat pull-secret for `crc start`

Quick checks:

```bash
make openshift.check
```

## 2) Start local OpenShift

```bash
make openshift.start
```

Load `oc` environment and login (required for apply/get):

```bash
eval "$(crc oc-env)"
oc login -u kubeadmin -p kubeadmin https://api.crc.testing:6443
```

If your cluster was configured with a generated password, fetch it with:

```bash
crc console --credentials
```

## 3) Bootstrap scheduler manifests

```bash
make openshift.bootstrap
```

This applies:

- `k8s/openshift/namespace.yaml`
- `k8s/openshift/trainingjob-crd.yaml`
- `k8s/openshift/secondary-scheduler-configmap.yaml`
- `k8s/openshift/mutating-webhook.yaml`

## 4) Submit dummy NYC Taxi job

```bash
make openshift.demo.nyc
```

Track status/logs:

```bash
make openshift.status
oc -n hackeurope26 logs job/nyc-taxi-dummy
```

Expected log output includes periodic `mse` and a final `predicted_fare_usd` line.

## 5) Optional local-only run (no cluster)

```bash
make run.nyc.taxi
```

## Notes

- The demo job includes label `energy-scheduling=true` and energy annotations, so it is compatible with the webhook flow.
- For full webhook mutation behavior, ensure the webhook service endpoint and TLS CA bundle are configured in your cluster.
