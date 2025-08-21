#!/usr/bin/env bash
set -euo pipefail

# Name: DL
# Case: DL
# α_base=0.25, α_peak=0.55 | C_mem=62GiB
# M0=15.5GiB, Mp=34.1GiB, ΔM=18.6GiB | threads≈29, util≈0.95
# CPU-centric training: modest M0 with per-epoch temporaries that lift RSS toward Mp; very high thread count and utilization. Good for CPU co-scheduling and safety under spikes.

./hpc_phase_sim --name=DL \
	--phase type=mem,abs=15.5G \
	--phase type=cpu,threads=29,util=0.95,duration=107s \
	--phase type=mem,delta=+18.6G \
	--phase type=sleep,duration=8s \
	--phase type=mem,delta=-18.6G \
	--phase type=cpu,threads=29,util=0.91,duration=124s \
	--phase type=mem,delta=+18.6G \
	--phase type=sleep,duration=13s \
	--phase type=mem,delta=-18.6G \
	--phase type=cpu,threads=27,util=0.89,duration=217s
