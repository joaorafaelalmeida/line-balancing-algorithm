"""
Baseline methods used to benchmark the graph-based greedy heuristic:

  - Exact MILP (SALBP-2 with per-task RA, Method 2) solved with HiGHS via PuLP,
    lexicographic: (1) minimise the maximum station load, (2) with that load fixed,
    minimise the total absolute deviation from the mean station load.
  - Ranked Positional Weight (RPW, Helgeson & Birnie 1961) adapted to a fixed number
    of stations by bisection on the station capacity (Scholl 1999).
  - Scholl (1999) benchmark reader and Finco et al. (2020) energy-expenditure generator.
"""

import math
import random
import time
from collections import defaultdict

import pulp


# ── instances ────────────────────────────────────────────────────────────────

def read_in2_file(in2_file):
    """
    Reads a Scholl (1999) .IN2 precedence graph.

    :param in2_file: Path to the .IN2 file.
    :return: A tuple (tasks, precedence) with tasks as task_id -> time and precedence as a list of (a, b).
    """
    with open(in2_file, 'r') as file:
        lines = [line.strip() for line in file if line.strip()]
    n = int(lines[0])
    tasks = {str(i + 1): float(lines[1 + i]) for i in range(n)}
    precedence = []
    for line in lines[1 + n:]:
        a, b = (part.strip() for part in line.split(','))
        if a == '-1':
            break
        precedence.append((a, b))
    return tasks, precedence


# Beta(a, b) shape parameters for the metabolic work rate, Finco et al. (2020), Table 4
MWR_PROFILES = {
    'MWR1': (1, 8), 'MWR2': (1, 4), 'MWR3': (2, 8),
    'MWR4': (3, 8), 'MWR5': (2, 4), 'MWR6': (3, 4),
}

def generate_metabolic_costs(tasks, profile, seed=0):
    """
    Generates task energy expenditures following Finco et al. (2020):
    MWR(j) = 2 + 8 * Beta(a, b) [kCal/min], e(j) = MWR(j) * t(j) / 60 [kCal].

    :param tasks: dict of task_id -> time [s]
    :param profile: One of MWR_PROFILES.
    :param seed: Random seed.
    :return: dict of task_id -> energy [kCal]
    """
    a, b = MWR_PROFILES[profile]
    rng = random.Random(seed)
    return {t: (2 + 8 * rng.betavariate(a, b)) * tasks[t] / 60 for t in tasks}


# ── precedence helpers ───────────────────────────────────────────────────────

def transitive_closure(task_ids, precedence):
    """
    Returns all (transitive) successors and predecessors of each task.

    :param task_ids: Iterable of task IDs.
    :param precedence: A list of tuples representing precedence constraints.
    :return: A tuple (successors, predecessors), each task_id -> set of task IDs.
    """
    direct = defaultdict(list)
    for a, b in precedence:
        direct[a].append(b)
    successors = {}
    for t in task_ids:
        seen, stack = set(), list(direct[t])
        while stack:
            s = stack.pop()
            if s not in seen:
                seen.add(s)
                stack.extend(direct[s])
        successors[t] = seen
    predecessors = {t: set() for t in task_ids}
    for t, succ in successors.items():
        for s in succ:
            predecessors[s].add(t)
    return successors, predecessors


def station_windows(weights, successors, predecessors, n_operators, capacity):
    """
    Earliest/latest feasible station of each task for a given station capacity.

    :param weights: dict of task_id -> load contribution (time or energy).
    :param capacity: Upper bound on the station load.
    :return: dict of task_id -> (earliest, latest), 1-indexed.
    """
    eps = 1e-9
    windows = {}
    for t in weights:
        head = weights[t] + sum(weights[p] for p in predecessors[t])
        tail = weights[t] + sum(weights[s] for s in successors[t])
        earliest = max(1, math.ceil(head / capacity - eps))
        latest = min(n_operators, n_operators + 1 - math.ceil(tail / capacity - eps))
        windows[t] = (earliest, latest)
    return windows


# ── RPW heuristic ────────────────────────────────────────────────────────────

def rpw_pack(weights, precedence, positional_weights, capacity):
    """
    Station-oriented RPW packing for a given station capacity.

    :return: A list of stations, each a list of task IDs.
    """
    indegree = defaultdict(int)
    direct = defaultdict(list)
    for a, b in precedence:
        direct[a].append(b)
        indegree[b] += 1
    available = [t for t in weights if indegree[t] == 0]
    stations, current, load = [], [], 0.0
    while available:
        fitting = [t for t in available if load + weights[t] <= capacity + 1e-9]
        if not fitting:
            if not current:
                return None  # a single task exceeds the capacity
            stations.append(current)
            current, load = [], 0.0
            continue
        task = max(fitting, key=lambda t: positional_weights[t])
        current.append(task)
        load += weights[task]
        available.remove(task)
        for s in direct[task]:
            indegree[s] -= 1
            if indegree[s] == 0:
                available.append(s)
    stations.append(current)
    return stations


def rpw_salbp2(weights, precedence, n_operators, tol=1e-3):
    """
    RPW for a fixed number of stations: bisection on the capacity, returning the
    smallest-capacity RPW packing that uses at most n_operators stations.

    :param weights: dict of task_id -> load contribution (time or energy).
    :return: A dict station_id -> list of task IDs.
    """
    successors, _ = transitive_closure(weights, precedence)
    positional_weights = {t: weights[t] + sum(weights[s] for s in successors[t]) for t in weights}
    lo = max(max(weights.values()), sum(weights.values()) / n_operators)
    hi = sum(weights.values())
    best = rpw_pack(weights, precedence, positional_weights, hi)
    while hi - lo > tol * lo:
        mid = (lo + hi) / 2
        stations = rpw_pack(weights, precedence, positional_weights, mid)
        if stations is not None and len(stations) <= n_operators:
            hi, best = mid, stations
        else:
            lo = mid
    return {k + 1: tasks for k, tasks in enumerate(best)}


# ── MILP ─────────────────────────────────────────────────────────────────────

def solve_milp(times, metabolic_costs, precedence, n_operators, objective='TIME', alpha=0.5,
               upper_bound_solution=None, time_limit=60, smooth=True):
    """
    Exact SALBP-2 MILP with a fixed number of stations, solved with HiGHS.

    Objectives (stage 1, min-max load):
      TIME            min  max_k sum_i t'_i x_ik
      METABOLIC_COST  min  max_k sum_i e_i x_ik
      BOTH            min  alpha * z_C + (1 - alpha) * z_M, with the station loads normalised by
                      their targets (sum t' / K and sum e / K)
    Stage 2 (smooth=True) fixes the stage-1 objective and minimises the total absolute
    deviation of the station loads from their targets (L1 proxy for the Smoothness Index).

    :param times: dict of task_id -> RA-adjusted time t'_i [s]
    :param metabolic_costs: dict of task_id -> energy e_i [kCal]
    :param upper_bound_solution: Optional feasible assignment (station -> tasks) used to tighten
                                 station windows; any optimal solution remains feasible.
    :param time_limit: Time limit per stage [s].
    :return: A dict with 'assignment', 'status', 'objective', 'bound', 'gap', 'runtime'.
    """
    task_ids = list(times)
    K = n_operators
    ct_target = sum(times.values()) / K
    mc_target = sum(metabolic_costs.values()) / K
    successors, predecessors = transitive_closure(task_ids, precedence)

    # station windows from the heuristic upper bound (valid for all solutions at least as good)
    windows = {t: (1, K) for t in task_ids}
    if upper_bound_solution is not None:
        loads_c = [sum(times[t] for t in s) for s in upper_bound_solution.values()]
        loads_m = [sum(metabolic_costs[t] for t in s) for s in upper_bound_solution.values()]
        if objective == 'TIME':
            bounds = [(times, max(loads_c))]
        elif objective == 'METABOLIC_COST':
            bounds = [(metabolic_costs, max(loads_m))]
        else:
            # z_C <= ub / alpha and z_M <= ub / (1 - alpha) for any solution with objective <= ub
            ub = alpha * max(loads_c) / ct_target + (1 - alpha) * max(loads_m) / mc_target
            bounds = []
            if alpha > 0:
                bounds.append((times, ub / alpha * ct_target))
            if alpha < 1:
                bounds.append((metabolic_costs, ub / (1 - alpha) * mc_target))
        for weights, capacity in bounds:
            w = station_windows(weights, successors, predecessors, K, capacity)
            windows = {t: (max(windows[t][0], w[t][0]), min(windows[t][1], w[t][1])) for t in task_ids}

    model = pulp.LpProblem('SALBP2_RA', pulp.LpMinimize)
    x = {(t, k): pulp.LpVariable(f'x_{t}_{k}', cat='Binary')
         for t in task_ids for k in range(windows[t][0], windows[t][1] + 1)}
    station_of = {t: pulp.lpSum(k * x[t, k] for k in range(windows[t][0], windows[t][1] + 1)) for t in task_ids}
    for t in task_ids:
        model += pulp.lpSum(x[t, k] for k in range(windows[t][0], windows[t][1] + 1)) == 1
    for a, b in precedence:
        model += station_of[a] <= station_of[b]
    load_c = {k: pulp.lpSum(times[t] * x[t, k] for t in task_ids if (t, k) in x) for k in range(1, K + 1)}
    load_m = {k: pulp.lpSum(metabolic_costs[t] * x[t, k] for t in task_ids if (t, k) in x) for k in range(1, K + 1)}

    if objective == 'TIME':
        c = pulp.LpVariable('c', lowBound=max(max(times.values()), ct_target))
        for k in load_c:
            model += load_c[k] <= c
        stage1 = c
    elif objective == 'METABOLIC_COST':
        m = pulp.LpVariable('m', lowBound=max(max(metabolic_costs.values()), mc_target))
        for k in load_m:
            model += load_m[k] <= m
        stage1 = m
    else:
        z_c = pulp.LpVariable('z_c', lowBound=1)
        z_m = pulp.LpVariable('z_m', lowBound=1)
        for k in load_c:
            model += load_c[k] <= z_c * ct_target
            model += load_m[k] <= z_m * mc_target
        stage1 = alpha * z_c + (1 - alpha) * z_m
    model += stage1

    solver = pulp.HiGHS(msg=False, timeLimit=time_limit)
    start = time.time()
    model.solve(solver)
    runtime = time.time() - start
    status = pulp.LpStatus[model.status]
    if model.sol_status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return {'assignment': None, 'status': status, 'objective': None, 'bound': None, 'gap': None, 'runtime': runtime}

    objective_value = pulp.value(stage1)
    bound = model.solverModel.getInfo().mip_dual_bound
    gap = max(0.0, (objective_value - bound) / objective_value) if objective_value else 0.0
    optimal = gap <= 1e-4

    def current_assignment():
        assignment = defaultdict(list)
        for (t, k), var in x.items():
            if var.value() is not None and var.value() > 0.5:
                assignment[k].append(t)
        return {k: assignment.get(k, []) for k in range(1, K + 1)}

    assignment = current_assignment()
    smoothed = False

    if smooth:
        model += stage1 <= objective_value + 1e-6
        dev_c = {k: pulp.LpVariable(f'dc_{k}', lowBound=0) for k in load_c}
        dev_m = {k: pulp.LpVariable(f'dm_{k}', lowBound=0) for k in load_m}
        for k in load_c:
            model += dev_c[k] >= load_c[k] - ct_target
            model += dev_c[k] >= ct_target - load_c[k]
            model += dev_m[k] >= load_m[k] - mc_target
            model += dev_m[k] >= mc_target - load_m[k]
        w_c = {'TIME': 1.0, 'METABOLIC_COST': 0.0}.get(objective, alpha)
        model.setObjective(w_c * pulp.lpSum(dev_c.values()) / ct_target
                           + (1 - w_c) * pulp.lpSum(dev_m.values()) / mc_target)
        start = time.time()
        model.solve(pulp.HiGHS(msg=False, timeLimit=time_limit))
        runtime += time.time() - start
        # keep the stage-1 solution if stage 2 finds nothing within the time limit
        if model.sol_status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
            assignment = current_assignment()
            smoothed = True

    return {
        'assignment': assignment,
        'smoothed': smoothed,
        'status': 'Optimal' if optimal else 'Feasible',
        'objective': objective_value,
        'bound': bound,
        'gap': gap,
        'runtime': runtime,
    }


# ── evaluation ───────────────────────────────────────────────────────────────

def validate_assignment(assignment, task_ids, precedence):
    """
    Checks that every task is assigned exactly once and precedence holds on station order.

    :param assignment: dict station_id -> list of task IDs (station ids give the line order).
    :return: A list of error messages (empty when valid).
    """
    errors = []
    station_of = {}
    for k, ts in assignment.items():
        for t in ts:
            if t in station_of:
                errors.append(f'task {t} assigned twice')
            station_of[t] = k
    missing = set(task_ids) - set(station_of)
    if missing:
        errors.append(f'{len(missing)} tasks unassigned')
    violations = [(a, b) for a, b in precedence if a in station_of and b in station_of and station_of[a] > station_of[b]]
    if violations:
        errors.append(f'{len(violations)} precedence violations')
    return errors


def evaluate(assignment, raw_times, adjusted_times, metabolic_costs, n_operators):
    """
    Common performance metrics computed from the task-to-station assignment, so that every method is
    scored on the same basis: RA-adjusted station times (Method 2) and raw energy.
    Stations left empty count as zero load.

    :return: A dict of metrics.
    """
    loads_c = [sum(adjusted_times[t] for t in ts) for ts in assignment.values()]
    loads_m = [sum(metabolic_costs[t] for t in ts) for ts in assignment.values()]
    loads_c += [0.0] * (n_operators - len(loads_c))
    loads_m += [0.0] * (n_operators - len(loads_m))
    ct_target = sum(adjusted_times.values()) / n_operators
    mc_target = sum(metabolic_costs.values()) / n_operators
    cycle_time = max(loads_c)
    return {
        'stations_used': sum(1 for ts in assignment.values() if ts),
        'stations_total': len(assignment),
        'cycle_time': cycle_time,
        'max_metabolic': max(loads_m),
        'si_c': math.sqrt(sum((ct_target - l) ** 2 for l in loads_c)),
        'si_m': math.sqrt(sum((mc_target - l) ** 2 for l in loads_m)),
        'efficiency': sum(raw_times.values()) / (n_operators * cycle_time),
    }
