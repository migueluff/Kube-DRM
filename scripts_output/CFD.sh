#!/usr/bin/env bash
set -euo pipefail

# Name: CFD
# Case: CFD
# α_base=0.36, α_peak=0.62 | C_mem=62GiB
# M0=22.1GiB, Mp=38.6GiB, ΔM=16.5GiB | threads≈28, util≈0.88
# CFD-like: baseline mesh (M0) with long compute phases; periodic checkpoint/collective spikes raise RSS to Mp before releasing. Good for testing fast limit raises and hysteresis.

./hpc_phase_sim --name=CFD \
	--phase type=mem,abs=22.1G \
	--phase type=cpu,threads=28,util=0.88,duration=315s \
	--phase type=mem,delta=+16.5G \
	--phase type=sleep,duration=19s \
	--phase type=mem,delta=-12.4G \
	--phase type=cpu,threads=26,util=0.88,duration=109s \
	--phase type=mem,delta=+10.7G \
	--phase type=sleep,duration=43s \
	--phase type=mem,delta=-10.7G \
	--phase type=cpu,threads=24,util=0.86,duration=315s
