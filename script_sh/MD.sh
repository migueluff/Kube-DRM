#!/usr/bin/env bash
set -euo pipefail

# Name: MD-1
# Case: Molecular Dynamics (steady working set + neighbor-list spikes)
# Explanation: Holds a steady footprint with rare short spikes (NL rebuilds / I/O),
# then releases back to baseline. Friendly to co-runners most of the time; spikes
# check that limits have headroom without constant resizing. Peak mem ≈ 26 GiB.

./hpc_phase_sim --name=MD-1 \
	--phase type=mem,abs=20.0G \
	--phase type=cpu,threads=12,util=0.70,duration=600s \
	--phase type=mem,delta=+6.0G \
	--phase type=sleep,duration=15s \
	--phase type=mem,delta=-6.0G \
	--phase type=cpu,threads=8,util=0.60,duration=300s
