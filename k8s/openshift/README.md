# OpenShift Remote Cluster Setup

This folder contains manifests and commands to deploy to an online OpenShift cluster and submit a simple NYC Taxi dummy ML workload.

## 1) Install prerequisites

- OpenShift CLI (`oc`)
- Access to a remote cluster (Developer Sandbox, ROSA, ARO, IBM Cloud)

Quick check:

```bash
make openshift.check
```

## 2) Login to remote OpenShift

```bash
make openshift.login
```

Or run the command copied from your cluster web console:

```bash
oc login --token=sha256~xxxxx --server=https://api.<cluster-id>.openshiftapps.com:6443
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

On Developer Sandbox, cluster-scoped resources are skipped automatically if your user lacks permission.

## 4) Submit dummy NYC Taxi job

```bash
make openshift.demo.nyc
```

Track status/logs:

```bash
make openshift.status
oc logs -n "$(oc project -q)" job/nyc-taxi-dummy
```

Expected log output includes periodic `mse` and a final `predicted_fare_usd` line.

## 5) Optional local-only run (no cluster)

```bash
make run.nyc.taxi
```

## Notes

- The demo job includes label `energy-scheduling=true` and energy annotations, so it is compatible with the webhook flow.
- For full webhook mutation behavior, ensure the webhook service endpoint and TLS CA bundle are configured in your cluster.
