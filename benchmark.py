"""
Benchmark of the graph-based greedy heuristic against RPW and an exact MILP (HiGHS).

  results/benchmark_case.csv    — hot water boiler line, K = 3..10
  results/benchmark_scholl.csv  — 13 Scholl (1999) instances x K = 5..10 x 6 energy profiles (Finco et al. 2020)

Every method is scored with baselines.evaluate (RA-adjusted station times, raw energy) and every
assignment is checked for completeness and precedence feasibility.

Usage: python benchmark.py [case|scholl|all] [--workers N] [--time-limit S]
"""

import argparse
import csv
import os
import time
from multiprocessing import Pool

from algorithm import (
    read_data_file, read_precedence_file, compute_per_task_ra_times, Workstation,
    distribution_based_on_time, distribution_based_on_metabolic_cost, distribution_considering_both,
)
from baselines import (
    read_in2_file, generate_metabolic_costs, MWR_PROFILES,
    rpw_salbp2, solve_milp, validate_assignment, evaluate,
)

RESULTS_DIR = "results"
SCHOLL_DIR = "files/scholl"
SCHOLL_INSTANCES = ["ARC83", "BUXEY", "GUNTHER", "HAHN", "KILBRID", "LUTZ1", "LUTZ2",
                    "LUTZ3", "MUKHERJE", "SAWYER30", "TONGE70", "WARNECKE", "WEE-MAG"]
ALPHA = 0.5
FIELDS = ["instance", "profile", "n_tasks", "K", "ra_overhead_pct", "ra_overhead_pct_mawl43", "method",
          "cycle_time", "max_metabolic", "si_c", "si_m", "efficiency", "objective_both",
          "stations_used", "runtime_s", "milp_status", "milp_gap", "valid"]


def as_assignment(workstations):
    return {k: list(ws.get_tasks()) for k, ws in sorted(workstations.items())}


def run_config(config):
    """
    Runs every method on one (instance, profile, K) configuration.

    :param config: A tuple (instance, profile, tasks, metabolic_costs, precedence, K, time_limit).
    :return: A list of result rows.
    """
    instance, profile, tasks, metabolic_costs, precedence, K, time_limit = config
    adjusted = compute_per_task_ra_times(tasks, metabolic_costs)
    adjusted_43 = compute_per_task_ra_times(tasks, metabolic_costs, mawl=4.3)
    ct_target = sum(adjusted.values()) / K
    mc_target = sum(metabolic_costs.values()) / K

    solutions = {}

    def timed(name, fn):
        Workstation.reset_idx()
        start = time.time()
        assignment = fn()
        solutions[name] = (assignment, time.time() - start, None)

    timed("Greedy-TIME (original)", lambda: as_assignment(distribution_based_on_time(
        tasks, metabolic_costs, precedence, ct_target, 0, K, capacity_search=False)))
    timed("Greedy-MC (original)", lambda: as_assignment(distribution_based_on_metabolic_cost(
        tasks, metabolic_costs, precedence, mc_target, 0, K, capacity_search=False)))
    timed("Greedy-BOTH (original)", lambda: as_assignment(distribution_considering_both(
        tasks, metabolic_costs, precedence, ct_target, mc_target, 0, K, alpha=ALPHA,
        capacity_search=False, local_search=False)))
    timed("Greedy-TIME (capacity search)", lambda: as_assignment(distribution_based_on_time(
        tasks, metabolic_costs, precedence, ct_target, 0, K, local_search=False)))
    timed("Greedy-MC (capacity search)", lambda: as_assignment(distribution_based_on_metabolic_cost(
        tasks, metabolic_costs, precedence, mc_target, 0, K, local_search=False)))
    timed("Greedy-BOTH (capacity search)", lambda: as_assignment(distribution_considering_both(
        tasks, metabolic_costs, precedence, ct_target, mc_target, 0, K, alpha=ALPHA, local_search=False)))
    timed("Greedy-TIME", lambda: as_assignment(distribution_based_on_time(
        tasks, metabolic_costs, precedence, ct_target, 0, K)))
    timed("Greedy-MC", lambda: as_assignment(distribution_based_on_metabolic_cost(
        tasks, metabolic_costs, precedence, mc_target, 0, K)))
    timed("Greedy-BOTH", lambda: as_assignment(distribution_considering_both(
        tasks, metabolic_costs, precedence, ct_target, mc_target, 0, K, alpha=ALPHA)))
    timed("RPW-TIME", lambda: rpw_salbp2(adjusted, precedence, K))
    timed("RPW-MC", lambda: rpw_salbp2(metabolic_costs, precedence, K))

    for objective, warm in [("TIME", "Greedy-TIME"), ("METABOLIC_COST", "Greedy-MC"), ("BOTH", "Greedy-BOTH")]:
        upper = solutions[warm][0]
        if validate_assignment(upper, tasks, precedence):
            upper = None
        result = solve_milp(adjusted, metabolic_costs, precedence, K, objective, alpha=ALPHA,
                            upper_bound_solution=upper, time_limit=time_limit)
        solutions[f"MILP-{objective}"] = (result["assignment"], result["runtime"], result)

    rows = []
    for method, (assignment, runtime, milp) in solutions.items():
        row = {
            "instance": instance, "profile": profile, "n_tasks": len(tasks), "K": K,
            "ra_overhead_pct": (sum(adjusted.values()) / sum(tasks.values()) - 1) * 100,
            "ra_overhead_pct_mawl43": (sum(adjusted_43.values()) / sum(tasks.values()) - 1) * 100,
            "method": method, "runtime_s": runtime,
            "milp_status": milp["status"] if milp else "",
            "milp_gap": milp["gap"] if milp and milp["gap"] is not None else "",
        }
        if assignment is None:
            row["valid"] = False
        else:
            errors = validate_assignment(assignment, tasks, precedence)
            metrics = evaluate(assignment, tasks, adjusted, metabolic_costs, K)
            row.update(metrics)
            row["objective_both"] = ALPHA * metrics["cycle_time"] / ct_target + (1 - ALPHA) * metrics["max_metabolic"] / mc_target
            row["valid"] = not errors
        rows.append({f: row.get(f, "") for f in FIELDS})
    return rows


def run(configs, out_file, workers):
    """
    Runs the configurations in parallel, appending rows to out_file and skipping configurations already present.
    """
    done = set()
    if os.path.exists(out_file):
        with open(out_file) as f:
            done = {(r["instance"], r["profile"], int(r["K"])) for r in csv.DictReader(f)}
    pending = [c for c in configs if (c[0], c[1], c[5]) not in done]
    print(f"{out_file}: {len(pending)} configurations to run ({len(done)} already done)")
    new_file = not os.path.exists(out_file)
    with open(out_file, "a", newline="") as f, Pool(workers) as pool:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for i, rows in enumerate(pool.imap_unordered(run_config, pending), 1):
            writer.writerows(rows)
            f.flush()
            print(f"  [{i}/{len(pending)}] {rows[0]['instance']} {rows[0]['profile']} K={rows[0]['K']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Benchmark the greedy heuristic against RPW and MILP.")
    parser.add_argument("which", nargs="?", default="all", choices=["case", "scholl", "all"])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--time-limit", type=int, default=60, help="MILP time limit per stage [s].")
    args = parser.parse_args()
    os.makedirs(RESULTS_DIR, exist_ok=True)

    if args.which in ("case", "all"):
        tasks, metabolic_costs = read_data_file("files/data.txt")
        precedence = read_precedence_file("files/precedencediagram.dot")
        configs = [("BOILER", "MEM", tasks, metabolic_costs, precedence, K, args.time_limit) for K in range(3, 11)]
        run(configs, os.path.join(RESULTS_DIR, "benchmark_case.csv"), args.workers)

    if args.which in ("scholl", "all"):
        configs = []
        for instance in SCHOLL_INSTANCES:
            tasks, precedence = read_in2_file(os.path.join(SCHOLL_DIR, f"{instance}.IN2"))
            for seed, profile in enumerate(MWR_PROFILES):
                metabolic_costs = generate_metabolic_costs(tasks, profile, seed=seed)
                for K in range(5, 11):
                    configs.append((instance, profile, tasks, metabolic_costs, precedence, K, args.time_limit))
        run(configs, os.path.join(RESULTS_DIR, "benchmark_scholl.csv"), args.workers)


if __name__ == "__main__":
    main()
