#!/usr/bin/env bash
set -euo pipefail

# Name: ANL-1
# Case: Analytics / ETL (big load, bursty compute, long waits, shrink)
# Explanation: Allocates a sizable dataset, alternates short CPU bursts with long
# “I/O waits” (sleeps), then aggressively shrinks. Ideal to test downscaling of
# requests during calm phases while keeping limits safe during transient growth.
# Peak mem ≈ 24 GiB; moderate CPU.

./hpc_phase_sim --name=ANL-1 \
	--phase type=mem,abs=16.0G \
	--phase type=cpu,threads=6,util=0.35,duration=30s \
	--phase type=sleep,duration=60s \
	--phase type=cpu,threads=6,util=0.40,duration=40s \
	--phase type=sleep,duration=90s \
	--phase type=mem,delta=+8.0G \
	--phase type=sleep,duration=20s \
	--phase type=mem,delta=-12.0G \
	--phase type=cpu,threads=8,util=0.50,duration=120s
