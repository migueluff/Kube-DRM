#!/usr/bin/env bash
./hpc_phase_sim --name=var2_pulse_spikes \
  --phase type=mem,abs=8.0G \
  --phase type=cpu,threads=12,util=0.55,duration=210s \
  --phase type=mem,delta=+20.0G \
  --phase type=sleep,duration=35s \
  --phase type=mem,delta=-20.0G \
  --phase type=cpu,threads=30,util=0.93,duration=300s \
  --phase type=mem,delta=+26.0G \
  --phase type=sleep,duration=40s \
  --phase type=mem,delta=-16.0G \
  --phase type=cpu,threads=20,util=0.7,duration=240s \
  --phase type=sleep,duration=15s \
  --phase type=mem,delta=+12.0G \
  --phase type=cpu,threads=14,util=0.48,duration=180s
