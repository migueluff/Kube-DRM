#!/usr/bin/env bash
set -euo pipefail

# Name: FFT
# Case: FFT
# α_base=0.25, α_peak=0.55 | C_mem=62GiB
# M0≈15.5GiB, Mp≈34.1GiB, staged ΔM≈18.6GiB | threads≈20, util≈0.82
# FFT/PDE-like: staged growth (planning/buffer setup) to Mp, plateau compute, staged release, and a late mini-spike. Good for multi-step resize logic and conservative limit downscaling.

./hpc_phase_sim --name=FFT \
	--phase type=mem,abs=8.0G \
	--phase type=mem,delta=+7.5G \
	--phase type=cpu,threads=20,util=0.82,duration=194s \
	--phase type=mem,delta=+18.6G \
	--phase type=cpu,threads=18,util=0.79,duration=90s \
	--phase type=mem,delta=-3.9G \
	--phase type=cpu,threads=16,util=0.74,duration=100s \
	--phase type=mem,delta=+4.0G \
	--phase type=sleep,duration=11s \
	--phase type=mem,delta=-4.0G
