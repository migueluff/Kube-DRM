#!/usr/bin/env bash
./hpc_phase_sim --name=var4_staged_plateau \
  --phase type=mem,abs=18.0G \
  --phase type=mem,delta=+12.0G \
  --phase type=cpu,threads=20,util=0.78,duration=300s \
  --phase type=mem,delta=+16.0G \
  --phase type=sleep,duration=30s \
  --phase type=mem,delta=+12.0G \
  --phase type=cpu,threads=24,util=0.84,duration=540s \
  --phase type=mem,delta=-10.0G \
  --phase type=sleep,duration=50s \
  --phase type=mem,delta=-14.0G \
  --phase type=cpu,threads=14,util=0.5,duration=210s \
  --phase type=sleep,duration=20s \
  --phase type=mem,delta=+4.0G \
  --phase type=cpu,threads=18,util=0.7,duration=240s
