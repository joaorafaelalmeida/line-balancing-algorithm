"""
Experimental analysis for:
  "Graph-based Optimization for Assembly Line Balancing Incorporating Metabolic Restrictions"
  Extended journal version — fatigue/Rest Allowance analysis (Finco 2018/2020, Price 1990)

Produces:
  results/fig1_mode_comparison.pdf       — workstation loads for TIME / METABOLIC / BOTH (n=5)
  results/fig2_operator_sensitivity.pdf  — efficiency & smoothness vs number of operators
  results/fig3_ra_task_analysis.pdf      — per-task ET, RA inflation, top inflated tasks
  results/fig4_ra_comparison.pdf         — TIME mode with vs without RA (n=5)
  results/fig5_threshold_sensitivity.pdf — effect of threshold on balance quality
  results/table1_summary.csv             — full metrics table (all modes × operators)
  results/table2_ra_tasks.csv            — RA inflation per task
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

from algorithm import (
    read_data_file, read_precedence_file,
    calculate_avg_cycle_time, calculate_avg_metabolic_cost,
    distribution_based_on_time, distribution_based_on_metabolic_cost,
    distribution_considering_both, compute_per_task_ra_times, Workstation,
)

# ── paths ────────────────────────────────────────────────────────────────────
DATA_FILE       = "files/data.txt"
PRECEDENCE_FILE = "files/precedencediagram.dot"
RESULTS_DIR     = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── publication style ────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":      "serif",
    "font.size":        11,
    "axes.titlesize":   12,
    "axes.labelsize":   11,
    "xtick.labelsize":  10,
    "ytick.labelsize":  10,
    "legend.fontsize":  10,
    "figure.dpi":       150,
    "savefig.dpi":      300,
    "savefig.bbox":     "tight",
})

COLORS = {
    "TIME":            "#2166ac",
    "METABOLIC_COST":  "#d6604d",
    "BOTH":            "#4dac26",
    "ra_off":          "#999999",
    "ra_on":           "#2166ac",
    "highlight":       "#f4a582",
}

# ── helpers ──────────────────────────────────────────────────────────────────

def run_mode(mode, tasks, metabolic_costs, precedence, n_operators, threshold=10, use_ra=True):
    Workstation.reset_idx()
    mc = calculate_avg_metabolic_cost(metabolic_costs, n_operators)
    if mode == "TIME":
        # CT_limit = sum(C') / k  (Algorithm 1): RA-adjusted target when use_ra
        ref_times = compute_per_task_ra_times(tasks, metabolic_costs) if use_ra else tasks
        ct = calculate_avg_cycle_time(ref_times, n_operators)
        return distribution_based_on_time(
            tasks, metabolic_costs, precedence, ct, threshold, n_operators, use_ra=use_ra
        )
    elif mode == "METABOLIC_COST":
        return distribution_based_on_metabolic_cost(
            tasks, metabolic_costs, precedence, mc, threshold, n_operators
        )
    elif mode == "BOTH":
        # Stage 1 TIME sub-solution uses the same RA-adjusted target as standalone TIME
        adj = compute_per_task_ra_times(tasks, metabolic_costs)
        ct = calculate_avg_cycle_time(adj, n_operators)
        Workstation.reset_idx()
        return distribution_considering_both(
            tasks, metabolic_costs, precedence, ct, mc, threshold, n_operators, alpha=0.5
        )


def smoothness_index(workstations, target, attr="cycle_time"):
    values = [getattr(ws, attr) for ws in workstations.values()]
    return float(np.sqrt(sum((target - v) ** 2 for v in values)))


def line_efficiency(workstations, total_raw_time):
    max_ct = max(ws.cycle_time for ws in workstations.values())
    return total_raw_time / (len(workstations) * max_ct)


def metrics(workstations, tasks, metabolic_costs, n_operators):
    ct_avg  = calculate_avg_cycle_time(tasks, n_operators)
    mc_avg  = calculate_avg_metabolic_cost(metabolic_costs, n_operators)
    times   = [ws.cycle_time   for ws in workstations.values()]
    energies= [ws.metabolic_cost for ws in workstations.values()]
    total_raw = sum(tasks.values())
    return {
        "n_workstations":   len(workstations),
        "max_cycle_time":   max(times),
        "min_cycle_time":   min(times),
        "avg_cycle_time":   np.mean(times),
        "target_ct":        ct_avg,
        "ct_violations":    sum(1 for t in times if t > ct_avg),
        "max_metabolic":    max(energies),
        "target_mc":        mc_avg,
        "mc_violations":    sum(1 for e in energies if e > mc_avg),
        "smoothness_index": smoothness_index(workstations, ct_avg),
        "line_efficiency":  line_efficiency(workstations, total_raw),
        "ra_overhead_pct":  (sum(tasks.values()) / total_raw - 1) * 100,  # placeholder
    }

# ── load data ────────────────────────────────────────────────────────────────
tasks, metabolic_costs = read_data_file(DATA_FILE)
precedence = read_precedence_file(PRECEDENCE_FILE)
total_raw_time = sum(tasks.values())
adjusted_times = compute_per_task_ra_times(tasks, metabolic_costs)

print(f"Tasks: {len(tasks)}  |  Precedence constraints: {len(precedence)}")
print(f"Total raw time: {total_raw_time:.1f}s")
print(f"Total RA-adjusted time: {sum(adjusted_times.values()):.1f}s  "
      f"(+{(sum(adjusted_times.values())/total_raw_time - 1)*100:.2f}%)")
print(f"Tasks with RA > 0: {sum(1 for t in tasks if adjusted_times[t] > tasks[t])}\n")

# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — Mode comparison: workstation loads (n=5, threshold=10)
# ═══════════════════════════════════════════════════════════════════════════════
print("Figure 1: mode comparison …")

N_OPS     = 5
THRESHOLD = 0
MODES     = ["TIME", "METABOLIC_COST", "BOTH"]
MODE_LABELS = {"TIME": "Time-Based", "METABOLIC_COST": "Metabolic-Based", "BOTH": "Consensus (Both)"}

# Normalized: each bar = metric / target  →  1.0 means exactly on target
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)

for ax, mode in zip(axes, MODES):
    ws     = run_mode(mode, tasks, metabolic_costs, precedence, N_OPS, THRESHOLD)
    ws_ids = list(ws.keys())
    # TIME mode is balanced against the RA-adjusted target; the other modes against the raw target
    ct_avg = calculate_avg_cycle_time(adjusted_times if mode == "TIME" else tasks, N_OPS)
    mc_avg = calculate_avg_metabolic_cost(metabolic_costs, N_OPS)

    norm_ct = [ws[i].cycle_time    / ct_avg for i in ws_ids]
    norm_mc = [ws[i].metabolic_cost / mc_avg for i in ws_ids]

    x = np.arange(len(ws_ids))
    w = 0.38
    ax.bar(x - w/2, norm_ct, w, label="Cycle time / target",    color=COLORS["TIME"],           alpha=0.85)
    ax.bar(x + w/2, norm_mc, w, label="Metabolic cost / target", color=COLORS["METABOLIC_COST"], alpha=0.85)
    ax.axhline(1.0, color="black", linestyle="--", linewidth=1.2, label="Target (= 1.0)")

    ax.set_title(MODE_LABELS[mode])
    ax.set_xlabel("Workstation")
    if ax is axes[0]:
        ax.set_ylabel("Load ratio (value / target)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"WS{i}" for i in ws_ids])
    ax.legend(fontsize=8.5, loc="upper right")
    ax.set_ylim(0, max(max(norm_ct), max(norm_mc)) * 1.25)

fig.suptitle(
    f"Normalised Workstation Load by Mode  (n = {N_OPS} operators, threshold = {THRESHOLD}%)\n"
    f"Values above 1.0 exceed the target; CT target = {calculate_avg_cycle_time(tasks, N_OPS):.0f}s, "
    f"MC target = {calculate_avg_metabolic_cost(metabolic_costs, N_OPS):.2f} kCal",
    fontsize=11, y=1.03,
)
fig.tight_layout()
fig.savefig(f"{RESULTS_DIR}/fig1_mode_comparison.pdf")
plt.close(fig)
print("  saved fig1_mode_comparison.pdf")

# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 2 — Operator sensitivity: efficiency & smoothness index vs n_operators
# ═══════════════════════════════════════════════════════════════════════════════
print("Figure 2: operator sensitivity …")

N_RANGE = range(3, 11)

results_sens = {mode: [] for mode in MODES}
for n in N_RANGE:
    for mode in MODES:
        ws = run_mode(mode, tasks, metabolic_costs, precedence, n, THRESHOLD)
        ct = calculate_avg_cycle_time(tasks, n)
        results_sens[mode].append({
            "n":                n,
            "efficiency":       line_efficiency(ws, total_raw_time),
            "smoothness_index": smoothness_index(ws, ct),
            "max_cycle_time":   max(w.cycle_time for w in ws.values()),
            "max_metabolic":    max(w.metabolic_cost for w in ws.values()),
        })

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

for mode in MODES:
    ns   = [r["n"]                for r in results_sens[mode]]
    eff  = [r["efficiency"]       for r in results_sens[mode]]
    si   = [r["smoothness_index"] for r in results_sens[mode]]
    axes[0].plot(ns, eff, marker="o", label=MODE_LABELS[mode], color=COLORS[mode])
    axes[1].plot(ns, si,  marker="s", label=MODE_LABELS[mode], color=COLORS[mode])

axes[0].set_xlabel("Number of Operators")
axes[0].set_ylabel("Line Efficiency")
axes[0].set_title("Line Efficiency vs Number of Operators")
axes[0].set_xticks(list(N_RANGE))
axes[0].legend()
axes[0].set_ylim(0, 1.05)
axes[0].axhline(1.0, color="black", linestyle="--", linewidth=0.8, alpha=0.5)

axes[1].set_xlabel("Number of Operators")
axes[1].set_ylabel("Smoothness Index")
axes[1].set_title("Smoothness Index vs Number of Operators")
axes[1].set_xticks(list(N_RANGE))
axes[1].legend()

fig.tight_layout()
fig.savefig(f"{RESULTS_DIR}/fig2_operator_sensitivity.pdf")
plt.close(fig)
print("  saved fig2_operator_sensitivity.pdf")

# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 3 — RA task-level analysis
# ═══════════════════════════════════════════════════════════════════════════════
print("Figure 3: RA task analysis …")

MAWL = 3.5
RELAX_RATE = 1.86

task_ids = list(tasks.keys())
et_vals  = [(metabolic_costs[t] / tasks[t]) * 60 for t in task_ids]
ra_vals  = [max(0, (et - MAWL) / (MAWL - RELAX_RATE)) for et in et_vals]
infl_pct = [(adjusted_times[t] / tasks[t] - 1) * 100 for t in task_ids]

# top 15 most inflated tasks
top15_idx = sorted(range(len(task_ids)), key=lambda i: -infl_pct[i])[:15]
top15_ids  = [task_ids[i] for i in top15_idx]
top15_raw  = [tasks[t]          for t in top15_ids]
top15_adj  = [adjusted_times[t] for t in top15_ids]
top15_et   = [et_vals[task_ids.index(t)] for t in top15_ids]

fig = plt.figure(figsize=(14, 5))
gs  = GridSpec(1, 2, figure=fig, wspace=0.35)

# --- left: scatter ET vs RA for all tasks
ax0 = fig.add_subplot(gs[0])
et_arr  = np.array(et_vals)
ra_arr  = np.array(ra_vals)
mask_ra = ra_arr > 0

ax0.scatter(et_arr[~mask_ra], ra_arr[~mask_ra], color="#aaaaaa", s=25, alpha=0.6, label="RA = 0")
ax0.scatter(et_arr[ mask_ra], ra_arr[ mask_ra], color=COLORS["highlight"], s=45,
            edgecolors="#cc3300", linewidths=0.6, label="RA > 0")
ax0.axvline(MAWL, color="red", linestyle="--", linewidth=1.2,
            label=f"MAWL = {MAWL} kCal/min")
ax0.set_xlabel("Energy-Time Ratio ET(j) [kCal/min]")
ax0.set_ylabel("Rest Allowance RA(j)")
ax0.set_title("Per-Task ET vs Rest Allowance")
ax0.legend()

# annotate a few extreme tasks
for t in top15_ids[:5]:
    i  = task_ids.index(t)
    ax0.annotate(f" {t}", (et_vals[i], ra_vals[i]), fontsize=7.5, color="#333333")

# --- right: grouped bar raw vs adjusted for top 15
ax1 = fig.add_subplot(gs[1])
x  = np.arange(len(top15_ids))
w  = 0.38
ax1.bar(x - w/2, top15_raw, w, label="Raw time",      color=COLORS["ra_off"], alpha=0.85)
ax1.bar(x + w/2, top15_adj, w, label="Adjusted time", color=COLORS["ra_on"],  alpha=0.85)
ax1.set_xticks(x)
ax1.set_xticklabels([f"T{t}" for t in top15_ids], rotation=45, ha="right", fontsize=9)
ax1.set_xlabel("Task ID")
ax1.set_ylabel("Time (s)")
ax1.set_title("Top 15 Tasks by RA Inflation (Raw vs Adjusted)")
ax1.legend()

# annotate ET above each adjusted bar
for i, t in enumerate(top15_ids):
    ax1.text(i + w/2, top15_adj[i] + 0.3, f"{top15_et[i]:.1f}", ha="center", fontsize=7.5)

fig.suptitle("Rest Allowance Analysis (MAWL = 3.5 kCal/min, Price 1990)", fontsize=12, y=1.02)
fig.savefig(f"{RESULTS_DIR}/fig3_ra_task_analysis.pdf")
plt.close(fig)
print("  saved fig3_ra_task_analysis.pdf")

# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 4 — RA comparison: TIME mode with vs without RA (n=5)
# ═══════════════════════════════════════════════════════════════════════════════
print("Figure 4: with vs without RA comparison …")

ct_base = calculate_avg_cycle_time(tasks, N_OPS)

Workstation.reset_idx()
ws_no_ra = distribution_based_on_time(
    tasks, metabolic_costs, precedence, ct_base, THRESHOLD, N_OPS, use_ra=False
)
Workstation.reset_idx()
ct_ra = calculate_avg_cycle_time(adjusted_times, N_OPS)
ws_ra = distribution_based_on_time(
    tasks, metabolic_costs, precedence, ct_ra, THRESHOLD, N_OPS, use_ra=True
)

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=False)

for ax, ws, label, ct_ref, use_ra_flag in [
    (axes[0], ws_no_ra, "Without Rest Allowance", ct_base, False),
    (axes[1], ws_ra,    "With Rest Allowance (MAWL = 3.5 kCal/min)", ct_ra, True),
]:
    ws_ids = list(ws.keys())
    times  = [ws[i].cycle_time for i in ws_ids]
    colors = [COLORS["ra_on"] if t <= ct_ref else COLORS["highlight"] for t in times]
    ax.bar(ws_ids, times, color=colors, alpha=0.85)
    ax.axhline(ct_ref, color="red", linestyle="--", linewidth=1.4,
               label=f"Cycle time target ({ct_ref:.0f}s)")
    ax.set_title(label)
    ax.set_xlabel("Workstation")
    ax.set_ylabel("Cycle Time (s)")
    ax.set_xticks(ws_ids)
    ax.set_xticklabels([f"WS{i}" for i in ws_ids])
    ax.legend()
    ax.set_ylim(0, max(times) * 1.2)
    for i, (ws_id, t) in enumerate(zip(ws_ids, times)):
        ax.text(ws_id, t + 2, f"{t:.0f}s", ha="center", fontsize=9)

over_no_ra = sum(1 for ws in ws_no_ra.values() if ws.cycle_time > ct_base)
over_ra    = sum(1 for ws in ws_ra.values()    if ws.cycle_time > ct_ra)
axes[0].set_title(f"Without RA  (violations: {over_no_ra}/{N_OPS})")
axes[1].set_title(f"With RA (violations: {over_ra}/{N_OPS})")

fig.suptitle(f"Impact of Rest Allowance on Cycle Time Distribution (n = {N_OPS} operators)",
             fontsize=12, y=1.01)
fig.tight_layout()
fig.savefig(f"{RESULTS_DIR}/fig4_ra_comparison.pdf")
plt.close(fig)
print("  saved fig4_ra_comparison.pdf")

# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 5 — Threshold sensitivity (TIME mode, RA on, n=5)
# ═══════════════════════════════════════════════════════════════════════════════
print("Figure 5: threshold sensitivity …")

THRESHOLDS = [0, 5, 10, 15, 20]
ct_ra_ref  = calculate_avg_cycle_time(adjusted_times, N_OPS)

thresh_metrics = []
for thr in THRESHOLDS:
    Workstation.reset_idx()
    ws = distribution_based_on_time(
        tasks, metabolic_costs, precedence, ct_ra_ref, thr, N_OPS, use_ra=True
    )
    thresh_metrics.append({
        "threshold":        thr,
        "max_ct":           max(w.cycle_time for w in ws.values()),
        "min_ct":           min(w.cycle_time for w in ws.values()),
        "smoothness_index": smoothness_index(ws, ct_ra_ref),
        "efficiency":       line_efficiency(ws, total_raw_time),
        "violations":       sum(1 for w in ws.values() if w.cycle_time > ct_ra_ref * (1 + thr / 100)),
    })

df_thr = pd.DataFrame(thresh_metrics)

fig, axes = plt.subplots(1, 3, figsize=(14, 4))

axes[0].plot(df_thr["threshold"], df_thr["smoothness_index"], marker="o", color=COLORS["TIME"])
axes[0].set_xlabel("Threshold (%)")
axes[0].set_ylabel("Smoothness Index")
axes[0].set_title("Smoothness Index vs Threshold")
axes[0].set_xticks(THRESHOLDS)

axes[1].plot(df_thr["threshold"], df_thr["efficiency"], marker="s", color=COLORS["METABOLIC_COST"])
axes[1].set_xlabel("Threshold (%)")
axes[1].set_ylabel("Line Efficiency")
axes[1].set_title("Line Efficiency vs Threshold")
axes[1].set_xticks(THRESHOLDS)
axes[1].set_ylim(0, 1.05)

df_thr["spread"] = df_thr["max_ct"] - df_thr["min_ct"]
axes[2].plot(df_thr["threshold"], df_thr["spread"], marker="^", color=COLORS["BOTH"])
axes[2].set_xlabel("Threshold (%)")
axes[2].set_ylabel("Load Spread, Max − Min CT (s)")
axes[2].set_title("Load Spread vs Threshold")
axes[2].set_xticks(THRESHOLDS)

fig.suptitle(f"Threshold Sensitivity Analysis (TIME mode + RA, n = {N_OPS} operators)",
             fontsize=12, y=1.02)
fig.tight_layout()
fig.savefig(f"{RESULTS_DIR}/fig5_threshold_sensitivity.pdf")
plt.close(fig)
print("  saved fig5_threshold_sensitivity.pdf")

# ═══════════════════════════════════════════════════════════════════════════════
# TABLE 1 — Full metrics: all modes × operators 3–10
# ═══════════════════════════════════════════════════════════════════════════════
print("Table 1: full metrics table …")

rows = []
for n in N_RANGE:
    ct  = calculate_avg_cycle_time(tasks, n)
    mc  = calculate_avg_metabolic_cost(metabolic_costs, n)
    ct_adj = calculate_avg_cycle_time(adjusted_times, n)
    for mode in MODES:
        use_ra = (mode == "TIME")
        ws = run_mode(mode, tasks, metabolic_costs, precedence, n, THRESHOLD, use_ra=use_ra)
        times    = [w.cycle_time    for w in ws.values()]
        energies = [w.metabolic_cost for w in ws.values()]
        ref_ct   = ct_adj if use_ra else ct
        rows.append({
            "Mode":              mode,
            "Operators":         n,
            "Target CT (s)":     round(ref_ct, 2),
            "Target MC (kCal)":  round(mc, 4),
            "Max CT (s)":        round(max(times), 2),
            "Min CT (s)":        round(min(times), 2),
            "Avg CT (s)":        round(np.mean(times), 2),
            "CT Violations":     sum(1 for t in times if t > ref_ct * (1 + THRESHOLD / 100)),
            "Max MC (kCal)":     round(max(energies), 4),
            "MC Violations":     sum(1 for e in energies if e > mc * (1 + THRESHOLD / 100)),
            "Smoothness Index":  round(smoothness_index(ws, ref_ct), 2),
            "Line Efficiency":   round(line_efficiency(ws, total_raw_time), 4),
        })

df_table1 = pd.DataFrame(rows)
df_table1.to_csv(f"{RESULTS_DIR}/table1_summary.csv", index=False)

# print a compact view
print(df_table1[["Mode", "Operators", "Max CT (s)", "CT Violations",
                  "Max MC (kCal)", "MC Violations", "Smoothness Index",
                  "Line Efficiency"]].to_string(index=False))

# ═══════════════════════════════════════════════════════════════════════════════
# TABLE 2 — RA inflation per task (all tasks with RA > 0)
# ═══════════════════════════════════════════════════════════════════════════════
print("\nTable 2: RA inflation per task …")

ra_rows = []
for t in task_ids:
    ET = (metabolic_costs[t] / tasks[t]) * 60
    RA = max(0, (ET - MAWL) / (MAWL - RELAX_RATE))
    if RA > 0:
        ra_rows.append({
            "Task":         t,
            "Raw time (s)": round(tasks[t], 3),
            "Energy (kCal)":round(metabolic_costs[t], 3),
            "ET (kCal/min)":round(ET, 3),
            "RA":           round(RA, 4),
            "Adj time (s)": round(adjusted_times[t], 3),
            "Inflation (%)":round((adjusted_times[t]/tasks[t] - 1)*100, 2),
        })

df_table2 = pd.DataFrame(ra_rows).sort_values("RA", ascending=False).reset_index(drop=True)
df_table2.to_csv(f"{RESULTS_DIR}/table2_ra_tasks.csv", index=False)
print(df_table2.to_string(index=False))

# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 6 — Alpha sensitivity in BOTH mode (n=5, threshold=10)
# ═══════════════════════════════════════════════════════════════════════════════
print("\nFigure 6: alpha sensitivity in BOTH mode …")

ALPHAS = [0.0, 0.25, 0.5, 0.75, 1.0]
ALPHA_LABELS = {0.0: "α=0\n(metabolic only)", 0.25: "α=0.25", 0.5: "α=0.5\n(equal)", 0.75: "α=0.75", 1.0: "α=1\n(time only)"}

# Stage-1 TIME sub-solution uses the RA-adjusted target (consistent with run_mode/
# standalone TIME); the raw target is the reference for SI, violations, and
# normalisation (consistent with metrics() and Tables 3/4).
ct_stage1 = calculate_avg_cycle_time(compute_per_task_ra_times(tasks, metabolic_costs), N_OPS)
ct_ref    = calculate_avg_cycle_time(tasks, N_OPS)
mc_avg5   = calculate_avg_metabolic_cost(metabolic_costs, N_OPS)

alpha_rows = []
for alpha in ALPHAS:
    Workstation.reset_idx()
    ws = distribution_considering_both(
        tasks, metabolic_costs, precedence, ct_stage1, mc_avg5, THRESHOLD, N_OPS, alpha=alpha
    )
    times    = [w.cycle_time    for w in ws.values()]
    energies = [w.metabolic_cost for w in ws.values()]
    alpha_rows.append({
        "alpha":            alpha,
        "max_norm_ct":      max(t / ct_ref for t in times),
        "max_norm_mc":      max(e / mc_avg5 for e in energies),
        "smoothness_ct":    smoothness_index(ws, ct_ref),
        "smoothness_mc":    smoothness_index(ws, mc_avg5, attr="metabolic_cost"),
        "ct_violations":    sum(1 for t in times if t > ct_ref),
        "mc_violations":    sum(1 for e in energies if e > mc_avg5),
    })

df_alpha = pd.DataFrame(alpha_rows)

fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
x = np.arange(len(ALPHAS))
w = 0.38

# panel 1: max normalised load per objective
axes[0].plot(ALPHAS, df_alpha["max_norm_ct"], marker="o", color=COLORS["TIME"],           label="Max CT / target")
axes[0].plot(ALPHAS, df_alpha["max_norm_mc"], marker="s", color=COLORS["METABOLIC_COST"], label="Max MC / target")
axes[0].axhline(1.0, color="black", linestyle="--", linewidth=0.9)
axes[0].set_xlabel("Alpha (α)")
axes[0].set_ylabel("Max load ratio (value / target)")
axes[0].set_title("Maximum Station Load vs α")
axes[0].set_xticks(ALPHAS)
axes[0].legend()

# panel 2: smoothness index per objective (separate axes: CT in s, MC in kCal)
l1, = axes[1].plot(ALPHAS, df_alpha["smoothness_ct"], marker="o", color=COLORS["TIME"], label="Smoothness (CT)")
axes[1].set_xlabel("Alpha (α)")
axes[1].set_ylabel("$SI_C$ (s)", color=COLORS["TIME"])
axes[1].tick_params(axis="y", labelcolor=COLORS["TIME"])
axes[1].set_title("Smoothness Index vs α")
axes[1].set_xticks(ALPHAS)
ax1b = axes[1].twinx()
l2, = ax1b.plot(ALPHAS, df_alpha["smoothness_mc"], marker="s", color=COLORS["METABOLIC_COST"], label="Smoothness (MC)")
ax1b.set_ylabel("$SI_M$ (kCal)", color=COLORS["METABOLIC_COST"])
ax1b.tick_params(axis="y", labelcolor=COLORS["METABOLIC_COST"])
axes[1].legend(handles=[l1, l2], loc="upper right", fontsize=8.5)

# panel 3: violations per objective
bw = 0.18
axes[2].bar(x - bw, df_alpha["ct_violations"], bw*2, label="CT violations", color=COLORS["TIME"],           alpha=0.85)
axes[2].bar(x + bw, df_alpha["mc_violations"], bw*2, label="MC violations", color=COLORS["METABOLIC_COST"], alpha=0.85)
axes[2].set_xlabel("Alpha (α)")
axes[2].set_ylabel("Workstations exceeding target")
axes[2].set_title("Target Violations vs α")
axes[2].set_xticks(x)
axes[2].set_xticklabels([ALPHA_LABELS[a] for a in ALPHAS], fontsize=9)
axes[2].legend()

fig.suptitle(
    f"Effect of Conflict-Resolution Weight α on BOTH Mode  (n = {N_OPS}, threshold = {THRESHOLD}%)\n"
    "α = 1 → prioritise cycle time; α = 0 → prioritise metabolic cost; α = 0.5 → equal weight",
    fontsize=11, y=1.03,
)
fig.tight_layout()
fig.savefig(f"{RESULTS_DIR}/fig6_alpha_sensitivity.pdf")
plt.close(fig)
print("  saved fig6_alpha_sensitivity.pdf")

print(f"\nAll results saved to ./{RESULTS_DIR}/")
