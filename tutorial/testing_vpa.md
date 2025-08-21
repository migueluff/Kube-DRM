# Testing the VPA Vertical Auto-Scaling

In order to understand exactly what Kubernetes offers in terms of autoscaling and how it works, I decided to use Minikube and conduct a small test to observe autoscaling in practice. This simple test helped me better understand the concepts used by Kubernetes and observe autoscaling in real time. Before we start, let's define some of these concepts.

> ⚠️ **Note**: To support in-place vertical scaling, you must use a VM-based driver like `kvm2` with Minikube. The Docker driver does not support container runtimes (like containerd) in a way that enables in-place resource resizing.

## Pods Have QoS Classes

Pods are classified into three distinct QoS classes:
i) **Guaranteed**,
ii) **Burstable**, and
iii) **BestEffort**.

This classification is done automatically based on the `requests` and `limits` specified in the deployment file. The QoS class also determines the pod's eviction priority. Yes, pods can be evicted when there is high resource pressure on a node. The classes are defined as follows:

| `requests` = `limits` | `requests` set | `limits` set | QoS Class  | Eviction Priority |
| --------------------- | -------------- | ------------ | ---------- | ----------------- |
| Yes                   | Yes            | Yes          | Guaranteed | Lowest            |
| No                    | Yes            | Yes          | Burstable  | Medium            |
| No                    | Yes            | No           | Burstable  | Medium            |
| No                    | No             | No           | BestEffort | Highest           |

### Alright, but what does each QoS class mean in terms of resource usage?

From the perspective of the resource usage policy, the classes play an important role: they determine whether a pod can exceed its requested resources.

* In the case of the **Guaranteed** class, the pod cannot exceed the specified resources because the `requests` and `limits` are set to the same values. However, the requested resources are allocated exclusively for this pod, ensuring stable performance.

* In the case of the **Burstable** class, as the name suggests, the pod can exceed the requested resources up to the defined limit. This means it gets a guaranteed minimum (the request), but it can use more if the node has available capacity, up to the limit.

* In the case of the **BestEffort** class, there are no resource requests or limits defined. As a result, the pod receives CPU and memory resources only when they are available, and it can be the first to be evicted when the node is under pressure.

Things get more interesting when we start to look at how these `requests` and `limits` are used from the scheduler's point of view. For scheduling purposes, what matters is the **requested** resource, not the limit. Let’s say we have only pods in the **Guaranteed** class and a compute node available. In this case, the scheduler will assign pods to the node as long as the **requested** resources fit within the node’s available capacity. For example, if a node has `x` units of a resource (e.g., CPU or memory), and each pod requests `y` units, then the maximum number of pods that can be scheduled on that node is approximately `x / y`.

The same principle applies to the Burstable class: the scheduler considers only the requested resources when deciding where to place the pod. It will schedule the pod on a compute node only if the available resources are sufficient to accommodate the request.

It’s important to note that in Kubernetes, the definition of “available resources” at scheduling time does not refer to the actual real-time usage of CPU or memory. Instead, it is based on the sum of all requested resources from the pods already scheduled on the node. The scheduler subtracts this total from the node’s capacity to determine what is still available.

### Now, We Can Talk About Vertical Auto-Scaling

Vertical auto-scaling in Kubernetes does **change the amount of resources a container can use** — but not dynamically at runtime (at least not traditionally). What it actually does is update the value of the **`requests`** field — especially for pods in the **Burstable** class — and, if configured, it can also update **`limits`**.

And that makes a lot of sense if you think about the scheduling challenges this class introduces. I have a set of applications that are telling me they need a certain amount of resources — but I’m nice, so I allow them to use up to a limit. Then I make all my scheduling decisions based on the requested value they gave me (because I’m nice... but also very naive to believe applications). And that brings a lot of problems during long-running executions. Why? Because I’ll end up placing way more applications on the node than I should. Eventually, they’ll all start using more than they asked for, and everyone’s performance will suffer — all thanks to the applications I never should’ve trusted in the first place.

And that’s exactly the problem the Vertical Pod Autoscaler (VPA) tries to solve. It observes the resource usage of applications over time and **recommends new `requests` values**. Traditionally, applying these new values required **restarting the pod**, which could be disruptive — especially for stateful or long-running workloads.

But starting from Kubernetes v1.27, there's a new mechanism: **in-place vertical scaling**. With this feature enabled, Kubernetes can **update a pod's resource requests (and sometimes limits) without restarting it**. This allows for smoother autoscaling behavior, avoiding downtime while still correcting under-provisioned pods.

## Testing the in-place vertical scaling

Now, let's do a small test to verify how the in-place vertical scaling works.

## Step 1: Start Minikube with `kvm2` Driver and Required Feature Gate

To support in-place resizing, **do not use the Docker driver**. Instead:

```bash
minikube delete  # If you already have a cluster

minikube start \
  --driver=kvm2 \
  --container-runtime=containerd \
  --feature-gates=InPlacePodVerticalScaling=true \
  --cpus=4 \
  --memory=4096 \
  --kubernetes-version=v1.32.0
```

---

## Step 2: Enable Metrics Server (Required for VPA)

```bash
minikube addons enable metrics-server
```

Wait \~15 seconds and verify:

```bash
kubectl get pods -n kube-system | grep metrics-server
```

---

## Step 3: Deploy Vertical Pod Autoscaler

If not already done:

```bash
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler
./hack/vpa-up.sh
```

Verify VPA is running:

```bash
kubectl get pods -n kube-system | grep vpa
```

## Step 4: Deploy `nginx` with Very Low Requests

### `nginx-deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
        - name: nginx
          image: nginx
          resources:
            requests:
              cpu: "10m"
              memory: "20Mi"
            limits:
              cpu: "20m"
              memory: "1Gi"
```

Apply it:

```bash
kubectl apply -f nginx-deployment.yaml
```

---

## Step 5: Expose `nginx` as a Service

```bash
kubectl expose deployment nginx --port=80 --target-port=80 --name=nginx
```

---

## Step 6: Deploy the VPA for `nginx`

### `nginx-vpa.yaml`

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: nginx-vpa
spec:
  targetRef:
    apiVersion: "apps/v1"
    kind:       Deployment
    name:       nginx
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
      - containerName: "*"
        controlledResources: ["cpu", "memory"]
        controlledValues: "RequestsAndLimits"
        minAllowed:
          cpu: "10m"
          memory: "20Mi"
        maxAllowed:
          cpu: "2000m"
          memory: "1Gi"
```

Apply it:

```bash
kubectl apply -f nginx-vpa.yaml
```

---

## Step 7: Deploy Scalable `busybox` to Stress `nginx`

### `busybox-deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: busybox
spec:
  replicas: 1  # Start small, scale later
  selector:
    matchLabels:
      app: busybox
  template:
    metadata:
      labels:
        app: busybox
    spec:
      containers:
        - name: busybox
          image: busybox
          command: ["/bin/sh"]
          args: ["-c", "while true; do wget -q -O- http://nginx; done"]
```

Apply it:

```bash
kubectl apply -f busybox-deployment.yaml
```

Then scale it gradually:

```bash
kubectl scale deployment busybox --replicas=50
kubectl scale deployment busybox --replicas=100
kubectl scale deployment busybox --replicas=200
```

---

## Step 8: Observe VPA Behavior

### Monitor CPU:

```bash
watch -n 2 kubectl top pod -l app=nginx
```

### Check VPA Recommendation:

```bash
kubectl describe vpa nginx-vpa
```

### Confirm In-Place Update (no restart):

```bash
kubectl get pod -l app=nginx -o jsonpath='{.items[*].spec.containers[*].resources.requests}'
kubectl get pod -l app=nginx -o jsonpath='{.items[*].metadata.creationTimestamp}'
```

## Manually Resize the nginx Pod In-Place

To test in-place resizing without VPA, you can manually update a running pod's resources.

### Step A: Edit the Pod with Subresource Resize

```bash
kubectl get pod -l app=nginx
kubectl edit pod <nginx-pod-name> --subresource=resize
```

Update the CPU/memory requests and limits. For example:

```yaml
resources:
  requests:
    cpu: "250m"
    memory: "200Mi"
  limits:
    cpu: "500m"
    memory: "400Mi"
```

Save and exit.

### Step B: Confirm Resize Completed

```bash
kubectl get pod <nginx-pod-name> -o jsonpath='{.status.resize}'
```

If the output is empty (`""`), the resize has been completed.

### Step C: Check the New Resource Settings

```bash
kubectl get pod <nginx-pod-name> -o jsonpath='{.spec.containers[*].resources}'
```

### Step D: Verify No Pod Restart Occurred

```bash
kubectl describe pod <nginx-pod-name> | grep -i restart
```

This confirms in-place vertical scaling is working without a pod restart.

