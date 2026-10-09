# An Ergonomic Graph-Based Heuristic for Assembly Line Balancing with Rest Allowance

## Overview

This repository contains the implementation of a graph-based greedy heuristic for the Simple Assembly Line Balancing Problem with a fixed number of operators (SALBP-2), extended with two ergonomic dimensions: **rest allowance (RA)** and **metabolic cost**. The greedy construction is embedded in a capacity search and followed by a precedence-feasible local search. The method is benchmarked against an exact MILP model and the Ranked Positional Weight (RPW) heuristic.

The approach is validated on a real-world hot water boiler assembly line comprising **160 tasks** and **193 precedence constraints**, with metabolic expenditure estimated via MTM-UAS, and on **13 benchmark instances** from Scholl (1999).

This code accompanies the journal paper:

> *An Ergonomic Graph-Based Heuristic for Assembly Line Balancing with Rest Allowance* (under review)

## Method

- **Rest allowance**: per-task rest allowances are computed with the Price (1990) formula and used to inflate task times before balancing. The Maximum Acceptable Working Level is set by `MAWL` in `algorithm.py` (default 3.5 kCal/min).
- **Capacity search**: for a fixed number of operators, the station capacity is the smallest value, not below the ideal load, for which the greedy packing fits all tasks; it is found by bisection.
- **Local search**: precedence-feasible moves and swaps of tasks between stations, minimising the (weighted) maximum normalised station load, with the smoothness of the loads as tie-breaker.
- **Three distribution modes**:
  - `TIME` — balances the RA-adjusted cycle time.
  - `METABOLIC_COST` — balances the metabolic cost.
  - `BOTH` — reconciles the two through a normalised, $\alpha$-weighted conflict-resolution step, followed by local search.
- **Benchmarks** (`baselines.py`): exact MILP (solved with HiGHS via PuLP) and RPW with capacity search, both on the same RA-adjusted times.

## Repository Structure

```
├── main.py                  # CLI entry point
├── algorithm.py             # Graph-based greedy heuristic, capacity search and local search
├── baselines.py             # MILP model, RPW heuristic, Scholl reader, evaluation
├── experiments.py           # Case-study experiments (figures and tables of the paper)
├── benchmark.py             # Comparison with MILP and RPW (case study and Scholl instances)
├── analyze_benchmark.py     # Summary of the benchmark results
├── genetic_algorithm.py     # Earlier implementation (not used by the current code)
├── files/
│   ├── data.txt             # Task cycle times and metabolic costs (case study)
│   ├── precedencediagram.dot  # Precedence constraints (DOT format)
│   └── scholl/              # 13 Scholl (1999) instances (.IN2)
└── results/                 # Figures and tables produced by the scripts
```

## Requirements

- Python 3.12+
- `numpy`, `pandas`, `matplotlib`
- `pulp` and `highspy` (MILP benchmark only)

```bash
pip install numpy pandas matplotlib pulp highspy
```

## Usage

```bash
python main.py <data_file> <precedence_file> <K> <MODE> [--threshold DELTA] [--alpha ALPHA] [--mawl MAWL]
```

| Argument | Description |
|----------|-------------|
| `data_file` | Path to task data file (cycle times and metabolic costs) |
| `precedence_file` | Path to DOT precedence diagram |
| `K` | Number of operators (workstations) |
| `MODE` | Distribution mode: `TIME`, `METABOLIC_COST`, or `BOTH` |
| `--threshold` | Overload tolerance $\delta$ in % (default: `0`) |
| `--alpha` | Weight of cycle time in BOTH mode, $\alpha \in [0,1]$ (default: `0.5`) |
| `--mawl` | Maximum Acceptable Working Level in kCal/min (default: `3.5`) |

Example (BOTH mode, 5 operators):
```bash
python main.py files/data.txt files/precedencediagram.dot 5 BOTH --alpha 0.5
```

## Input Format

**`data.txt`** — one task per line, space-separated:
```
<task_id>  <cycle_time_s>  <metabolic_cost_kcal>
```

**`precedencediagram.dot`** — standard DOT directed graph:
```dot
digraph {
    1 -> 2
    1 -> 3
    ...
}
```

## Reproducing the Paper Results

```bash
python experiments.py                        # case-study figures and tables, incl. MAWL sensitivity
python benchmark.py case                     # case study: heuristic vs RPW vs MILP (K = 3..10)
python benchmark.py scholl --workers 6       # Scholl instances: 13 x K = 5..10 x 6 energy profiles
python analyze_benchmark.py                  # summary table of the benchmark
```

Outputs are written to `results/`. The Scholl benchmark runs the MILP with a 60 s limit per stage and takes several hours; it resumes from the configurations already saved in `results/benchmark_scholl.csv`. Energy expenditure for the Scholl instances is generated as in Finco et al. (2020), with fixed random seeds.

## Reference

If you use this code, please cite:

```
Paper details suppressed for blind review.
```

## License

This project is licensed under the MIT License.
