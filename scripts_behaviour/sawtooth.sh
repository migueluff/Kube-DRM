#!/usr/bin/env bash
./hpc_phase_sim --name=var3_sawtooth \
  --phase type=mem,abs=24.0G \
  --phase type=cpu,threads=28,util=0.92,duration=420s \
  --phase type=mem,delta=+18.0G \
  --phase type=sleep,duration=40s \
  --phase type=mem,delta=-8.0G \
  --phase type=cpu,threads=16,util=0.58,duration=240s \
  --phase type=mem,delta=+14.0G \
  --phase type=sleep,duration=45s \
  --phase type=mem,delta=-22.0G \
  --phase type=cpu,threads=30,util=0.89,duration=330s \
  --phase type=mem,delta=+30.0G \
  --phase type=sleep,duration=30s \
  --phase type=mem,delta=-20.0G \
  --phase type=cpu,threads=10,util=0.4,duration=180s
