#!/usr/bin/env bash
set -euo pipefail

# Name: MD
# Case: MD
# α_base=0.29, α_peak=0.55 | C_mem=62GiB
# M0=18.2GiB, Mp=34.1GiB, ΔM=15.9GiB | threads≈10, util≈0.66
# Molecular dynamics-like: steady working set M0 for long compute; brief neighbor-list/I-O spikes to Mp followed by immediate release. Good for minimal-churn, headroom-aware limits.

./hpc_phase_sim --name=MD \
	--phase type=mem,abs=18.2G \
	--phase type=cpu,threads=10,util=0.66,duration=300s \
	--phase type=mem,delta=+15.9G \
	--phase type=sleep,duration=46s \
	--phase type=mem,delta=-15.9G \
	--phase type=cpu,threads=8,util=0.61,duration=241s
