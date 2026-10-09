"""
Summarises results/benchmark_case.csv and results/benchmark_scholl.csv.

For each heuristic, the gap is measured against the MILP solved for the same objective:
  TIME methods  -> cycle time (RA-adjusted)      vs MILP-TIME
  MC methods    -> maximum station energy        vs MILP-METABOLIC_COST
  BOTH methods  -> alpha-weighted normalised max vs MILP-BOTH
A negative gap means the heuristic beat a MILP that hit its time limit.

Writes results/benchmark_summary.csv and results/benchmark_summary.tex.
"""

import os
import pandas as pd

RESULTS_DIR = "results"
GROUPS = {
    "TIME": ("cycle_time", "MILP-TIME", ["Greedy-TIME (original)", "Greedy-TIME (capacity search)", "Greedy-TIME", "RPW-TIME"]),
    "METABOLIC_COST": ("max_metabolic", "MILP-METABOLIC_COST", ["Greedy-MC (original)", "Greedy-MC (capacity search)", "Greedy-MC", "RPW-MC"]),
    "BOTH": ("objective_both", "MILP-BOTH", ["Greedy-BOTH (original)", "Greedy-BOTH (capacity search)", "Greedy-BOTH"]),
}


def summarise(df, dataset):
    assert df["valid"].astype(str).eq("True").all(), "invalid assignments in results"
    keys = ["instance", "profile", "K"]
    rows = []
    for objective, (metric, milp, methods) in GROUPS.items():
        ref = df[df.method == milp].set_index(keys)
        for method in methods + [milp]:
            m = df[df.method == method].set_index(keys)
            gap = (m[metric] / ref[metric] - 1) * 100
            rows.append({
                "dataset": dataset, "objective": objective, "method": method, "n": len(m),
                "mean_gap_pct": gap.mean(), "max_gap_pct": gap.max(),
                "pct_within_1pct": (gap <= 1).mean() * 100,
                "pct_matches_milp": (gap <= 1e-6).mean() * 100,
                "mean_runtime_s": m["runtime_s"].mean(), "max_runtime_s": m["runtime_s"].max(),
                "milp_optimal_pct": (ref["milp_status"] == "Optimal").mean() * 100,
            })
    return pd.DataFrame(rows)


def main():
    frames = []
    for dataset, file in [("Case study", "benchmark_case.csv"), ("Scholl", "benchmark_scholl.csv")]:
        path = os.path.join(RESULTS_DIR, file)
        if os.path.exists(path):
            df = pd.read_csv(path)
            frames.append(summarise(df, dataset))
            ra = df.drop_duplicates(["instance", "profile"])
            print(f"{dataset}: {len(df.drop_duplicates(['instance', 'profile', 'K']))} configurations; "
                  f"RA overhead MAWL 3.5 = {ra.ra_overhead_pct.mean():.2f}%, MAWL 4.3 = {ra.ra_overhead_pct_mawl43.mean():.2f}%")
    summary = pd.concat(frames, ignore_index=True)
    summary.to_csv(os.path.join(RESULTS_DIR, "benchmark_summary.csv"), index=False)
    pd.set_option("display.width", 200)
    print(summary.round(3).to_string(index=False))

    columns = ["dataset", "objective", "method", "mean_gap_pct", "max_gap_pct", "pct_within_1pct", "mean_runtime_s"]
    header = ["Dataset", "Objective", "Method", "Mean gap (\\%)", "Max gap (\\%)", "Within 1\\% (\\%)", "Mean time (s)"]
    lines = ["\\begin{tabular}{lllrrrr}", "\\toprule", " & ".join(header) + " \\\\", "\\midrule"]
    for _, r in summary[columns].iterrows():
        cells = [r.dataset, r.objective.replace("_", "\\_"), r.method] + [f"{r[c]:.2f}" for c in columns[3:]]
        lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    with open(os.path.join(RESULTS_DIR, "benchmark_summary.tex"), "w") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
