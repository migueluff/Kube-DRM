#!/usr/bin/env python3
"""
make_hpc_dataset.py — Generate five HPC archetype scripts for ./hpc_phase_sim
Protocol (paper-ready):
  - Node: 62 GiB RAM, 32 cores.
  - Node-sharing policy:
      α_base ∈ [0.25, 0.45] of RAM
      α_peak ∈ [0.55, 0.75] of RAM
      M0 = α_base * C_mem, Mp = α_peak * C_mem, ΔM = Mp - M0
  - Durations: compute ~ lognormal (2–10 min), waits ~ lognormal (10–120 s).
  - Threads: 8–30 (cap below 32); utilization u by archetype.

Output:
  jobs/CFD.sh, jobs/MD.sh, jobs/ANALYTICS.sh, jobs/FFT.sh, jobs/DL.sh
  submit_all.sh (optional), index.csv (optional)
"""

import argparse, csv, math, os, random, re
from dataclasses import dataclass
from typing import List, Tuple

# =========================
# Editable defaults
# =========================
NODE_MEM_GIB   = 62.0   # ← use 62 GiB, not 64
NODE_CORES     = 32

ALPHA_BASE_RANGE = (0.25, 0.45)
ALPHA_PEAK_RANGE = (0.55, 0.75)

# Lognormal bands (seconds)
COMPUTE_MEAN_S, COMPUTE_SIGMA, COMPUTE_MIN_S, COMPUTE_MAX_S = 360.0, 1.5, 120.0, 600.0  # ~6 min center
WAIT_MEAN_S,    WAIT_SIGMA,    WAIT_MIN_S,    WAIT_MAX_S    = 45.0,  1.6,  10.0,  120.0

# Target centers per archetype (for α sampling; still clamped to policy ranges)
ARCHETYPE_TARGETS = {
    "CFD":       dict(alpha_base=0.35, alpha_peak=0.63, threads=(24, 28), util=(0.88, 0.92)),
    "MD":        dict(alpha_base=0.30, alpha_peak=0.40, threads=(8, 12),   util=(0.60, 0.75)),
    "ANALYTICS": dict(alpha_base=0.25, alpha_peak=0.40, threads=(6, 8),    util=(0.35, 0.50)),
    "FFT":       dict(alpha_base=0.25, alpha_peak=0.38, threads=(16, 20),  util=(0.75, 0.85)),
    "DL":        dict(alpha_base=0.20, alpha_peak=0.45, threads=(28, 30),  util=(0.90, 0.95)),
}

EXPLANATION = {
    "CFD": (
        "CFD-like: baseline mesh (M0) with long compute phases; periodic checkpoint/collective "
        "spikes raise RSS to Mp before releasing. Good for testing fast limit raises and hysteresis."
    ),
    "MD": (
        "Molecular dynamics-like: steady working set M0 for long compute; brief neighbor-list/I-O "
        "spikes to Mp followed by immediate release. Good for minimal-churn, headroom-aware limits."
    ),
    "ANALYTICS": (
        "Analytics/ETL-like: allocate M0, run short CPU bursts separated by longer sleeps (I/O waits); "
        "transient growth toward Mp then an aggressive shrink. Good for downscaling requests in calm windows."
    ),
    "FFT": (
        "FFT/PDE-like: staged growth (planning/buffer setup) to Mp, plateau compute, staged release, "
        "and a late mini-spike. Good for multi-step resize logic and conservative limit downscaling."
    ),
    "DL": (
        "CPU-centric training: modest M0 with per-epoch temporaries that lift RSS toward Mp; "
        "very high thread count and utilization. Good for CPU co-scheduling and safety under spikes."
    ),
}

# =========================
# Helpers
# =========================

def clamp(x, lo, hi): 
    return max(lo, min(hi, x))

def draw_lognormal(mean, sigma, lo, hi):
    """Draw positive value with lognormal(mean≈mean, stdev multiplier≈sigma), clamped to [lo,hi]."""
    s = math.log(sigma) if sigma > 1.0 else 1e-6
    mu = math.log(max(mean, 1e-9)) - 0.5 * s * s
    val = random.lognormvariate(mu, s)
    return clamp(val, lo, hi)

def pick_alpha(center, band, lo, hi):
    """Sample α near center (±band) and clamp to [lo,hi]."""
    v = random.uniform(center - band, center + band)
    return clamp(v, lo, hi)

def fmt_gib(x):
    """One decimal GiB like '22.4G'."""
    return f"{x:.1f}G"

def slug(s):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", s).strip("-") or "job"

def multiline_command(bin_path: str, name: str, phases: List[str]) -> str:
    """Format exactly with trailing backslashes and tabs."""
    lines = [f"{bin_path} --name={name} \\"]
    for i, seg in enumerate(phases):
        cont = " \\" if i < len(phases) - 1 else ""
        lines.append(f"\t{seg}{cont}")
    return "\n".join(lines)

# =========================
# Phase builders (strings)
# =========================

def p_mem_abs(gib: float) -> str:
    return f"--phase type=mem,abs={fmt_gib(gib)}"

def p_mem_delta(delta_gib: float) -> str:
    """Emit +X.YG for increases and -X.YG for reductions (never omit the sign)."""
    if delta_gib >= 0:
        return f"--phase type=mem,delta=+{fmt_gib(delta_gib)}"
    else:
        return f"--phase type=mem,delta=-{fmt_gib(-delta_gib)}"

def p_cpu(threads: int, util: float, dur_s: int) -> str:
    return f"--phase type=cpu,threads={threads},util={util:.2f},duration={dur_s}s"

def p_sleep(dur_s: int) -> str:
    return f"--phase type=sleep,duration={dur_s}s"

# =========================
# Archetype generators
# =========================

def gen_cfd(bin_path: str, name: str) -> Tuple[str, str]:
    t = ARCHETYPE_TARGETS["CFD"]
    a_base = pick_alpha(t["alpha_base"], 0.05, *ALPHA_BASE_RANGE)
    a_peak = pick_alpha(t["alpha_peak"], 0.05, *ALPHA_PEAK_RANGE)
    M0 = a_base * NODE_MEM_GIB
    Mp = a_peak * NODE_MEM_GIB
    dM = Mp - M0

    th = random.randint(*t["threads"])
    util1 = random.uniform(*t["util"])
    util2 = clamp(util1 - 0.02, t["util"][0], t["util"][1])

    c1 = int(draw_lognormal(COMPUTE_MEAN_S, COMPUTE_SIGMA, COMPUTE_MIN_S, COMPUTE_MAX_S))
    c2 = int(draw_lognormal(COMPUTE_MEAN_S*0.75, COMPUTE_SIGMA, 90, COMPUTE_MAX_S))
    w1 = int(draw_lognormal(WAIT_MEAN_S, WAIT_SIGMA, WAIT_MIN_S, WAIT_MAX_S))
    w2 = int(draw_lognormal(WAIT_MEAN_S*0.8, WAIT_SIGMA, WAIT_MIN_S, WAIT_MAX_S))

    # Two spikes that never exceed Mp
    spike1 = round(dM, 1)
    release1 = round(max(spike1 * 0.75, 0.0), 1)
    spike2 = round(max(dM * 0.65, 0.0), 1)
    if M0 + spike2 > Mp:
        spike2 = round(max(Mp - M0, 0.0), 1)

    phases = [
        p_mem_abs(round(M0, 1)),
        p_cpu(th, util1, c1),
        p_mem_delta(+spike1),
        p_sleep(w1),
        p_mem_delta(-release1),          # ← will print with a leading '-'
        p_cpu(max(th-2, 8), util2, c2),
        p_mem_delta(+spike2),
        p_sleep(w2),
        p_mem_delta(-spike2),            # ← will print with a leading '-'
        p_cpu(max(th-4, 8), clamp(util2 - 0.02, 0.35, 0.99), c1),
    ]
    cmd = multiline_command(bin_path, name, phases)
    desc = (
        f"# α_base={a_base:.2f}, α_peak={a_peak:.2f} | C_mem={NODE_MEM_GIB:.0f}GiB\n"
        f"# M0={M0:.1f}GiB, Mp={Mp:.1f}GiB, ΔM={dM:.1f}GiB | threads≈{th}, util≈{util1:.2f}\n"
        f"# {EXPLANATION['CFD']}\n"
    )
    return cmd, desc

def gen_md(bin_path: str, name: str) -> Tuple[str, str]:
    t = ARCHETYPE_TARGETS["MD"]
    a_base = pick_alpha(t["alpha_base"], 0.04, *ALPHA_BASE_RANGE)
    a_peak = pick_alpha(t["alpha_peak"], 0.03, *ALPHA_PEAK_RANGE)
    M0 = a_base * NODE_MEM_GIB
    Mp = a_peak * NODE_MEM_GIB
    dM = Mp - M0

    th = random.randint(*t["threads"])
    util = random.uniform(*t["util"])
    c1 = int(draw_lognormal(COMPUTE_MEAN_S*1.1, COMPUTE_SIGMA, 300, 900))
    c2 = int(draw_lognormal(COMPUTE_MEAN_S*0.8, COMPUTE_SIGMA, 120, 480))
    wait = int(draw_lognormal(WAIT_MEAN_S, WAIT_SIGMA, WAIT_MIN_S, WAIT_MAX_S))

    phases = [
        p_mem_abs(round(M0, 1)),
        p_cpu(th, util, c1),
        p_mem_delta(round(+dM, 1)),
        p_sleep(wait),
        p_mem_delta(round(-dM, 1)),      # ← prints '-'
        p_cpu(max(th-2, 8), clamp(util - 0.05, 0.35, 0.95), c2),
    ]
    cmd = multiline_command(bin_path, name, phases)
    desc = (
        f"# α_base={a_base:.2f}, α_peak={a_peak:.2f} | C_mem={NODE_MEM_GIB:.0f}GiB\n"
        f"# M0={M0:.1f}GiB, Mp={Mp:.1f}GiB, ΔM={dM:.1f}GiB | threads≈{th}, util≈{util:.2f}\n"
        f"# {EXPLANATION['MD']}\n"
    )
    return cmd, desc

def gen_analytics(bin_path: str, name: str) -> Tuple[str, str]:
    t = ARCHETYPE_TARGETS["ANALYTICS"]
    a_base = pick_alpha(t["alpha_base"], 0.03, *ALPHA_BASE_RANGE)
    a_peak = pick_alpha(t["alpha_peak"], 0.04, *ALPHA_PEAK_RANGE)
    M0 = a_base * NODE_MEM_GIB
    Mp = a_peak * NODE_MEM_GIB
    dM = Mp - M0

    th = random.randint(*t["threads"])
    util1 = random.uniform(*t["util"])
    util2 = clamp(util1 + 0.05, t["util"][0], t["util"][1])
    b1 = int(draw_lognormal(30, 1.3, 20, 60))
    b2 = int(draw_lognormal(45, 1.3, 20, 70))
    s1 = int(draw_lognormal(60, 1.6, 40, 100))
    s2 = int(draw_lognormal(90, 1.6, 50, 120))
    w = int(draw_lognormal(20, 1.5, 10, 40))

    shrink = round(dM * 1.3, 1)  # shrink beyond the transient to emulate eviction
    phases = [
        p_mem_abs(round(M0, 1)),
        p_cpu(th, util1, b1),
        p_sleep(s1),
        p_cpu(th, util2, b2),
        p_sleep(s2),
        p_mem_delta(round(+dM, 1)),
        p_sleep(w),
        p_mem_delta(-shrink),            # ← prints '-'
        p_cpu(min(th+2, 10), clamp(util2, 0.35, 0.55), int(draw_lognormal(120, 1.4, 60, 240))),
    ]
    cmd = multiline_command(bin_path, name, phases)
    desc = (
        f"# α_base={a_base:.2f}, α_peak={a_peak:.2f} | C_mem={NODE_MEM_GIB:.0f}GiB\n"
        f"# M0={M0:.1f}GiB, Mp={Mp:.1f}GiB, ΔM={dM:.1f}GiB | threads≈{th}, util≈{util1:.2f}→{util2:.2f}\n"
        f"# {EXPLANATION['ANALYTICS']}\n"
    )
    return cmd, desc

def gen_fft(bin_path: str, name: str) -> Tuple[str, str]:
    t = ARCHETYPE_TARGETS["FFT"]
    a_base = pick_alpha(t["alpha_base"], 0.03, *ALPHA_BASE_RANGE)
    a_peak = pick_alpha(t["alpha_peak"], 0.03, *ALPHA_PEAK_RANGE)
    M0 = a_base * NODE_MEM_GIB  # use as early plateau
    Mp = a_peak * NODE_MEM_GIB
    dM = Mp - M0

    th = random.randint(*t["threads"])
    util = random.uniform(*t["util"])

    # Stage in ~equal steps from ~M0/3 → M0 → Mp
    stage1 = round(max(M0/3.0, 8.0), 1)
    stage2_add = round(max(M0 - stage1, 0.0), 1)
    stage3_add = round(max(dM, 0.0), 1)
    rel1 = round(max(M0 * 0.25, 2.0), 1)

    c1 = int(draw_lognormal(180, 1.4, 120, 300))
    c2 = int(draw_lognormal(150, 1.4, 90, 240))
    c3 = int(draw_lognormal(120, 1.3, 60, 180))
    w  = int(draw_lognormal(15, 1.3, 10, 30))

    phases = [
        p_mem_abs(stage1),
        p_mem_delta(+stage2_add),                     # reach ~M0
        p_cpu(th, util, c1),
        p_mem_delta(+stage3_add),                     # reach ~Mp
        p_cpu(max(th-2, 12), clamp(util-0.03, 0.6, 0.9), c2),
        p_mem_delta(-rel1),                           # staged release (prints '-')
        p_cpu(max(th-4, 12), clamp(util-0.08, 0.5, 0.85), c3),
        p_mem_delta(+min(4.0, round(dM*0.5,1))),      # late mini-spike (≤4 GiB)
        p_sleep(w),
        p_mem_delta(-min(4.0, round(dM*0.5,1))),      # mini-release (prints '-')
    ]
    cmd = multiline_command(bin_path, name, phases)
    desc = (
        f"# α_base={a_base:.2f}, α_peak={a_peak:.2f} | C_mem={NODE_MEM_GIB:.0f}GiB\n"
        f"# M0≈{M0:.1f}GiB, Mp≈{Mp:.1f}GiB, staged ΔM≈{dM:.1f}GiB | threads≈{th}, util≈{util:.2f}\n"
        f"# {EXPLANATION['FFT']}\n"
    )
    return cmd, desc

def gen_dl(bin_path: str, name: str) -> Tuple[str, str]:
    t = ARCHETYPE_TARGETS["DL"]
    a_base = pick_alpha(t["alpha_base"], 0.03, *ALPHA_BASE_RANGE)
    a_peak = pick_alpha(t["alpha_peak"], 0.04, *ALPHA_PEAK_RANGE)
    M0 = a_base * NODE_MEM_GIB
    Mp = a_peak * NODE_MEM_GIB
    dM = Mp - M0

    th = min(random.randint(*t["threads"]), NODE_CORES - 1)  # keep < 32
    util = random.uniform(*t["util"])

    epoch1 = int(draw_lognormal(120, 1.3, 90, 180))
    epoch2 = int(draw_lognormal(180, 1.3, 120, 240))
    epoch3 = int(draw_lognormal(180, 1.3, 120, 240))
    w1 = int(draw_lognormal(12, 1.3, 8, 20))
    w2 = int(draw_lognormal(15, 1.3, 10, 22))

    phases = [
        p_mem_abs(round(M0, 1)),
        p_cpu(th, util, epoch1),
        p_mem_delta(round(+dM, 1)),
        p_sleep(w1),
        p_mem_delta(round(-dM, 1)),                   # prints '-'
        p_cpu(th, clamp(util-0.4e-1, 0.7, 0.99), epoch2),
        p_mem_delta(round(+dM, 1)),
        p_sleep(w2),
        p_mem_delta(round(-dM, 1)),                   # prints '-'
        p_cpu(max(th-2, 20), clamp(util-0.06, 0.7, 0.99), epoch3),
    ]
    cmd = multiline_command(bin_path, name, phases)
    desc = (
        f"# α_base={a_base:.2f}, α_peak={a_peak:.2f} | C_mem={NODE_MEM_GIB:.0f}GiB\n"
        f"# M0={M0:.1f}GiB, Mp={Mp:.1f}GiB, ΔM={dM:.1f}GiB | threads≈{th}, util≈{util:.2f}\n"
        f"# {EXPLANATION['DL']}\n"
    )
    return cmd, desc

# =========================
# File writing
# =========================

HEADER_TEMPLATE = """#!/usr/bin/env bash
set -euo pipefail

# Name: {name}
# Case: {case}
{desc}"""

def write_script(path: str, name: str, case: str, desc: str, cmd: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(HEADER_TEMPLATE.format(name=name, case=case, desc=desc))
        f.write("\n")
        f.write(cmd)
        f.write("\n")
    os.chmod(path, 0o755)

# =========================
# Main
# =========================

def main():
    ap = argparse.ArgumentParser(description="Generate five HPC archetype scripts (policy-consistent).")
    ap.add_argument("--out-dir", type=str, default="jobs")
    ap.add_argument("--bin", type=str, default="./hpc_phase_sim")
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--index-csv", type=str, default="jobs/index.csv")
    ap.add_argument("--submit-all", type=str, default="submit_all.sh")
    args = ap.parse_args()

    random.seed(args.seed)
    out = []

    gens = [
        ("CFD", "CFD.sh", gen_cfd),
        ("MD", "MD.sh", gen_md),
        ("ANALYTICS", "ANALYTICS.sh", gen_analytics),
        ("FFT", "FFT.sh", gen_fft),
        ("DL", "DL.sh", gen_dl),
    ]

    for case, fname, fn in gens:
        name = case
        cmd, desc = fn(args.bin, name)
        path = os.path.join(args.out_dir, fname)
        write_script(path, name=name, case=case, desc=desc, cmd=cmd)
        out.append((name, case, path, cmd.replace("\n", "\\n")))

    # write index CSV
    if args.index_csv:
        os.makedirs(os.path.dirname(args.index_csv) or ".", exist_ok=True)
        with open(args.index_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["name","case","script_path","command_multiline"])
            for row in out: w.writerow(row)

    # write submit_all.sh
    if args.submit_all:
        with open(args.submit_all, "w") as f:
            f.write("#!/usr/bin/env bash\nset -euo pipefail\n\n")
            for _name, case, path, _cmd in out:
                f.write(f"echo 'Launching {case}'\n")
                f.write(f"{path} &\n")
            f.write("wait\n")
        os.chmod(args.submit_all, 0o755)

    print(f"Generated {len(out)} scripts in {args.out_dir}")
    print(f"Index CSV: {args.index_csv}")
    print(f"Master launcher: {args.submit_all}")

if __name__ == "__main__":
    main()
