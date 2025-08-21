#!/usr/bin/env bash
./hpc_phase_sim --name=var5_epochs \
  --phase type=mem,abs=12.0G \
  --phase type=cpu,threads=22,util=0.8,duration=240s \
  --phase type=mem,delta=+10.0G \
  --phase type=sleep,duration=25s \
  --phase type=mem,delta=-10.0G \
  --phase type=cpu,threads=16,util=0.55,duration=180s \
  --phase type=mem,delta=+11.0G \
  --phase type=sleep,duration=30s \
  --phase type=mem,delta=-11.0G \
  --phase type=cpu,threads=28,util=0.9,duration=300s \
  --phase type=mem,delta=+12.0G \
  --phase type=sleep,duration=35s \
  --phase type=mem,delta=-12.0G \
  --phase type=cpu,threads=12,util=0.45,duration=150s \
  --phase type=mem,delta=+32.0G \
  --phase type=sleep,duration=40s \
  --phase type=mem,delta=-20.0G \
  --phase type=cpu,threads=24,util=0.75,duration=210s
