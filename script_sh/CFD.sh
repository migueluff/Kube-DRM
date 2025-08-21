#!/usr/bin/env bash
set -euo pipefail

# Name: CFD-1
# Case: CFD (mesh + solver + periodic checkpoints)
# Explanation: Starts with a large mesh resident set, runs long CPU phases, and
# introduces checkpoint/collective spikes that temporarily raise RSS. Spikes can
# stress co-runners. Good for testing “raise limit first, then requests” logic.
# Peak mem ≈ 36 GiB on a 64 GiB node; high CPU (28 threads) can cause contention.

./hpc_phase_sim --name=CFD-1 \
	--phase type=mem,abs=24.0G \
	--phase type=cpu,threads=28,util=0.90,duration=240s \
	--phase type=mem,delta=+12.0G \
	--phase type=sleep,duration=30s \
	--phase type=mem,delta=-10.0G \
	--phase type=cpu,threads=28,util=0.88,duration=180s \
	--phase type=mem,delta=+8.0G \
	--phase type=sleep,duration=20s \
	--phase type=mem,delta=-8.0G \
	--phase type=cpu,threads=24,util=0.85,duration=240s
