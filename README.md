### Meeting Notes — July 3rd

#### **Topic: Vertical Resource Management in Kubernetes for HPC Applications**

---

### Background

Kubernetes recently introduced **in-place pod resizing**, which allows dynamic adjustment of memory and CPU for running pods without restarting them.

It also offers **Vertical Pod Autoscaler (VPA)**, which modifies a pod’s resource allocation by stopping and restarting it with new values.

When launching a pod, two values are specified:

* `request`: the guaranteed minimum resource allocation.
* `limit`: the maximum resource usage allowed.

Based on these, Kubernetes assigns a **QoS (Quality of Service) Class**:

| `requests` = `limits` | `requests` set | `limits` set | QoS Class  | Eviction Priority |
| --------------------- | -------------- | ------------ | ---------- | ----------------- |
| Yes                   | Yes            | Yes          | Guaranteed | Lowest            |
| No                    | Yes            | Yes          | Burstable  | Medium            |
| No                    | Yes            | No           | Burstable  | Medium            |
| No                    | No             | No           | BestEffort | Highest           |

**Note:** Kubernetes schedules pods based on `request` values. A *Burstable* pod may consume more than its requested resources (up to the `limit`), which can lead to performance degradation if this behavior is not well managed.

---

### Objective 01: Study Resource Bursting in HPC Workloads

**Goal:** Understand how HPC applications behave when configured as burstable. Identify which metrics should be captured. Study the native schedulign strategy of Kubernets (we may try to improve it in the future as well).

#### Step 1: Select Applications

Identified benchmarks:

* NAS benchmarks
* PARSEC ([GitHub link](https://github.com/bamos/parsec-benchmark))
* Synthetic application ([GitHub link](https://github.com/luanteylo/synthetic))

#### Step 2: Individual Execution and Profiling

* Run each application in isolation
* Capture memory and CPU usage over time
* Record recommendations provided by VPA

#### Step 3: Co-execution Experiments

* Choose combinations of applications
* Assign request and limit values based on Step 2
* Allow Kubernetes to schedule pods
* Measure:

  * Runtime
  * Resource utilization
  * Interference (compared to isolated runs)
  * Queue time

---

### Experimental Scenarios

#### Scenario 1 – Extreme

Emulates a situation with no knowledge of the application’s needs.

* `request`: Minimum value
* `limit`: Maximum value

**Expected behavior:** Very short queue time, but significant runtime degradation due to resource contention.

---

#### Scenario 2 – Guaranteed

No bursting is allowed.

* `request` = `limit` = average usage

**Expected behavior:** Higher queue time, but more stable and efficient execution.

---

#### Scenario 3 – Burst Clairvoyant

Simulates a scenario where we know both average and peak resource usage.

* `request`: average usage
* `limit`: peak usage

**Expected behavior:** Similar queue time to Scenario 2. Execution time may improve if bursts are not frequent or overlapping. Otherwise, it may approach Scenario 1.

---

### Objective 02: Improve Performance with In-Place Pod Resize

Evaluate dynamic resizing strategies during execution to improve application performance.

**Key questions:**

* Should resizing be based on fixed thresholds?
* Can a sliding window average improve stability?
* Can VPA recommendations guide online resizing decisions?



### MAIN GOAL

The main goal is to implement a resizing strategy that achieves better performance than Scenario 3, meaning we aim to improve application runtime across all three experimental scenarios.

We plan to submit the results to SSCAD (deadline in August 5). However, if the results are particularly strong, we may consider targeting a more prominent venue for submission.

---

### Cluster Setup

* 2-node cluster:

  * 1 control plane node
  * 1 worker node with 32 CPUs and 62 GB of memory

---

### References

* [RC-V: Vertical Resource Adaptivity for HPC Workloads in Containerized Environments](https://arxiv.org/pdf/2505.02964)
* [Exploring Potential for Non-Disruptive Vertical Auto Scaling and Resource Estimation in Kubernetes](https://par.nsf.gov/servlets/purl/10185523)
* [A Survey of Autoscaling in Kubernetes](https://www.researchgate.net/profile/Minh-Ngoc-Tran-3/publication/362145963_A_Survey_of_Autoscaling_in_Kubernetes/links/64c5ea03213ca521ea183c68/A-Survey-of-Autoscaling-in-Kubernetes.pdf?__cf_chl_tk=myRLGmOgKT5GejRyJQyMPNLLOF6BSq8l.e_RvaLNX.8-1751552032-1.0.1.1-ZArR_mRmyiYQJ6h30TRlNCGKDHUKuBQ.dRoqdKfTlUg)


