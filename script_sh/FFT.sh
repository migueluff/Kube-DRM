#!/usr/bin/env bash
set -euo pipefail

# Name: FFT-1
# Case: Staged FFT/PDE (ramp-up, plateau, staged release, late mini-spike)
# Explanation: Grows in steps as plans/buffers are created, sustains compute, then
# sheds memory in stages with a late small spike (e.g., transpose buffer). Useful
# to verify multi-step request/limit tracking and conservative limit downscaling.
# Peak mem ≈ 24 GiB; mixed CPU intensity.

./hpc_phase_sim --name=FFT-1 \
	--phase type=mem,abs=8.0G \
	--phase type=mem,delta=+8.0G \
	--phase type=cpu,threads=20,util=0.85,duration=180s \
	--phase type=mem,delta=+8.0G \
	--phase type=cpu,threads=20,util=0.85,duration=120s \
	--phase type=mem,delta=-6.0G \
	--phase type=cpu,threads=16,util=0.75,duration=120s \
	--phase type=mem,delta=+4.0G \
	--phase type=sleep,duration=15s \
	--phase type=mem,delta=-4.0G \
	--phase type=cpu,threads=12,util=0.60,duration=90s
