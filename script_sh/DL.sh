#!/usr/bin/env bash
set -euo pipefail

# Name: DL-1
# Case: CPU-heavy training loop (epochs with transient buffer growth)
# Explanation: Keeps a modest base footprint, runs CPU-saturating epochs, and
# allocates temporary buffers per epoch that are freed afterward. Stresses CPU
# co-scheduling (up to 32 threads) and tests that memory spikes are handled safely.
# Peak mem ≈ 24 GiB; very high CPU can hurt neighbors.

./hpc_phase_sim --name=DL-1 \
	--phase type=mem,abs=12.0G \
	--phase type=cpu,threads=32,util=0.95,duration=120s \
	--phase type=mem,delta=+8.0G \
	--phase type=sleep,duration=10s \
	--phase type=mem,delta=-8.0G \
	--phase type=cpu,threads=32,util=0.90,duration=180s \
	--phase type=mem,delta=+12.0G \
	--phase type=sleep,duration=15s \
	--phase type=mem,delta=-12.0G \
	--phase type=cpu,threads=28,util=0.85,duration=180s
