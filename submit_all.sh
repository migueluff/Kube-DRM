#!/usr/bin/env bash
set -euo pipefail

echo 'Launching CFD'
scripts_output/CFD.sh &
echo 'Launching MD'
scripts_output/MD.sh &
echo 'Launching ANALYTICS'
scripts_output/ANALYTICS.sh &
echo 'Launching FFT'
scripts_output/FFT.sh &
echo 'Launching DL'
scripts_output/DL.sh &
wait
