#!/usr/bin/env bash
set -euo pipefail

# Name: ANALYTICS
# Case: ANALYTICS
# α_base=0.27, α_peak=0.55 | C_mem=62GiB
# M0=16.5GiB, Mp=34.1GiB, ΔM=17.6GiB | threads≈7, util≈0.44→0.49
# Analytics/ETL-like: allocate M0, run short CPU bursts separated by longer sleeps (I/O waits); transient growth toward Mp then an aggressive shrink. Good for downscaling requests in calm windows.

./hpc_phase_sim --name=ANALYTICS \
	--phase type=mem,abs=16.5G \
	--phase type=cpu,threads=7,util=0.44,duration=25s \
	--phase type=sleep,duration=57s \
	--phase type=cpu,threads=7,util=0.49,duration=56s \
	--phase type=sleep,duration=50s \
	--phase type=mem,delta=+17.6G \
	--phase type=sleep,duration=24s \
	--phase type=mem,delta=-22.9G \
	--phase type=cpu,threads=9,util=0.49,duration=86s
