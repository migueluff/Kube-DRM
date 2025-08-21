#!/usr/bin/env bash
./hpc_phase_sim --name=var1_staircase \
  --phase type=mem,abs=14.0G \
  --phase type=cpu,threads=26,util=0.88,duration=360s \
  --phase type=mem,delta=+10.5G \
  --phase type=sleep,duration=25s \
  --phase type=mem,delta=+8.0G \
  --phase type=cpu,threads=18,util=0.62,duration=240s \
  --phase type=mem,delta=-6.0G \
  --phase type=sleep,duration=30s \
  --phase type=mem,delta=+5.0G \
  --phase type=cpu,threads=22,util=0.74,duration=300s \
  --phase type=sleep,duration=20s \
  --phase type=mem,delta=-9.5G \
  --phase type=cpu,threads=28,util=0.91,duration=180s
