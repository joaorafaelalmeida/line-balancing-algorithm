from collections import defaultdict
import matplotlib.pyplot as plt

# Rest allowance parameters (Price, 1990) [kCal/min]
MAWL = 3.5          # Maximum Acceptable Working Level (conservative base case; 4.3 in Finco et al. 2018, 2020)
REST_RATE = 1.86    # metabolic rate at standing rest

class Workstation:
    idx = 1

    def reset_idx():
        Workstation.idx = 1

    def get_overall_performance(workstations):
        """
        Returns the overall performance of the workstations.

        :param workstations: A dictionary where keys are workstation IDs, and values are Workstation objects.
        :return: A dictionary where keys are workstation IDs, and values are tuples containing the cycle time and metabolic cost.
        """
        overall_performance = {}
        for w_id in workstations:
            overall_performance[w_id] = workstations[w_id].get_performance()
        return overall_performance
    
    def __init__(self):
        self.id = Workstation.idx
        Workstation.idx += 1
        self.cycle_time = 0
        self.metabolic_cost = 0
        self.tasks = []

    def add_task(self, task_to_assign, task_time, task_metabolic_cost):
        """
        Adds a task to the workstation and updates the cycle time and metabolic cost.

        :param task_to_assign: The task to assign.
        :param task_time: The time of the task.
        :param task_metabolic_cost: The metabolic cost of the task.
        """
        self.tasks.append(task_to_assign)
        self.cycle_time += task_time
        self.metabolic_cost += task_metabolic_cost

    def get_adjusted_cycle_time(self):
        """
        Returns the fatigue-adjusted cycle time using station-level Rest Allowance (Price, 1990) — Method 3 (Finco 2020).
        RA_station = max(0, (Σe/Σt * 60 - MAWL) / (MAWL - REST_RATE))
        T'_station = Σt * (1 + RA_station)
        Note: when per-task RA is used (Method 2), cycle_time already includes rest allowance inflation.
        """
        if self.cycle_time == 0:
            return 0
        ET_station = (self.metabolic_cost / self.cycle_time) * 60  # kCal/min
        RA_station = max(0, (ET_station - MAWL) / (MAWL - REST_RATE))
        return self.cycle_time * (1 + RA_station)

    def get_performance(self):
        """
        Returns the performance of the workstation.

        :return: A tuple containing the cycle time and metabolic cost.
        """
        return self.cycle_time, self.metabolic_cost
    
    def get_tasks(self):
        """
        Returns the tasks assigned to the workstation.

        :return: A list of tasks.
        """
        return self.tasks
    

class Graph:
    def __init__(self, precedence, tasks, metabolic_costs):
        self.task_graph, self.indegree = self.build_precedence_graph(precedence)
        self.available_tasks = [task for task in self.task_graph if self.indegree[task] == 0]
        self.tasks_times = tasks
        self.tasks_metabolic_costs = metabolic_costs

    def build_precedence_graph(self, precedence):
        """
        Builds the precedence graph and indegree dictionary.

        :param precedence: A list of tuples representing precedence constraints.
        :return: A tuple containing the precedence graph and indegree dictionary.
        """
        task_graph = defaultdict(list)
        indegree = defaultdict(int)
        for a, b in precedence:
            task_graph[a].append(b)
            indegree[b] += 1
        return task_graph, indegree

    def remove_task(self, task):
        """
        Removes a task from the graph and updates the available tasks and indegree dictionary.

        :param task: The task to remove.
        """
        self.available_tasks.remove(task)
        for dependent_task in self.task_graph[task]:
            self.indegree[dependent_task] -= 1
            if self.indegree[dependent_task] == 0:
                self.available_tasks.append(dependent_task)
    
    def get_lowest_time_task(self):
        """
        Returns the task with the lowest time.

        :return: The task with the lowest time.
        """
        task_to_assign = self.available_tasks[0]
        for task in self.available_tasks:
            if self.tasks_times[task] < self.tasks_times[task_to_assign]:
                task_to_assign = task
        return task_to_assign
    
    def get_lowest_metabolic_cost_task(self):
        """
        Returns the task with the lowest metabolic cost.

        :return: The task with the lowest metabolic cost.
        """
        task_to_assign = self.available_tasks[0]
        for task in self.available_tasks:
            if self.tasks_metabolic_costs[task] < self.tasks_metabolic_costs[task_to_assign]:
                task_to_assign = task
        return task_to_assign
    

def read_data_file(data_file):
    """
    Reads the task data file and returns a dictionary of task times and metabolic costs.
    
    :param data_file: Path to the data file.
    :return: A dictionary of tasks with their times and metabolic costs.
    """
    tasks = {}
    metabolic_costs = {}
    with open(data_file, 'r') as file:
        for line in file:
            parts = line.strip().split()
            task_id = parts[0]
            time = float(parts[1])
            metabolic_cost = float(parts[2])
            tasks[task_id] = time
            metabolic_costs[task_id] = metabolic_cost
    return tasks, metabolic_costs

def read_precedence_file(precedence_file):
    """
    Reads the precedence file and returns a list of precedence constraints.
    
    :param precedence_file: Path to the precedence file.
    :return: A list of tuples representing precedence constraints.
    """
    precedence = []
    with open(precedence_file, 'r') as file:
        for line in file:
            if '->' in line:
                parts = line.strip().split('->')
                precedence.append((parts[0].strip(), parts[1].strip()))
    return precedence

def topological_order(tasks, precedence):
    """
    Returns the tasks in a topological order of the precedence graph.

    :param tasks: A dictionary (or iterable) of task IDs.
    :param precedence: A list of tuples representing precedence constraints.
    :return: A list of task IDs.
    """
    graph = Graph(precedence, {}, {})
    for t in tasks:
        if graph.indegree[t] == 0 and t not in graph.available_tasks:
            graph.available_tasks.append(t)
    order = []
    while graph.available_tasks:
        t = graph.available_tasks[0]
        order.append(t)
        graph.remove_task(t)
    return order

def is_precedence_feasible(station_of, precedence):
    """
    Checks that every task is assigned to a workstation not earlier than those of its predecessors.

    :param station_of: dict of task_id -> workstation ID.
    :param precedence: A list of tuples representing precedence constraints.
    :return: True if all precedence constraints hold.
    """
    return all(station_of[a] <= station_of[b] for a, b in precedence)

def calculate_avg_cycle_time(tasks, n_operators):
    """
    Calculate the average cycle time for the tasks.

    :param tasks: A dictionary where keys are task IDs, and values are processing times.
    :param n_operators: The number of operators available.
    :return: The average cycle time.
    """
    return sum(tasks.values()) / n_operators

def calculate_avg_metabolic_cost(metabolic_costs, n_operators):
    """
    Calculate the average metabolic cost for the tasks.

    :param metabolic_costs: A dictionary where keys are task IDs, and values are metabolic costs.
    :param n_operators: The number of operators available.
    :return: The average metabolic cost.
    """
    return sum(metabolic_costs.values()) / n_operators

def compute_per_task_ra_times(tasks, metabolic_costs, mawl=None):
    """
    Computes RA-adjusted task times using per-task Rest Allowance (Price, 1990) — Method 2 from Finco (2018).

    ET(j) = e(j)/t(j) * 60              [kCal/min]
    RA(j) = max(0, (ET(j) - mawl) / (mawl - REST_RATE))
    t'(j) = t(j) * (1 + RA(j))

    :param tasks: dict of task_id -> time [s]
    :param metabolic_costs: dict of task_id -> energy [kCal]
    :param mawl: Maximum Acceptable Working Level [kCal/min] (default: module-level MAWL)
    :return: dict of task_id -> RA-adjusted time [s]
    """
    if mawl is None:
        mawl = MAWL
    adjusted = {}
    for task_id in tasks:
        ET = (metabolic_costs[task_id] / tasks[task_id]) * 60
        RA = max(0, (ET - mawl) / (mawl - REST_RATE))
        adjusted[task_id] = tasks[task_id] * (1 + RA)
    return adjusted


def pack_workstations(weights, tasks, metabolic_costs, precedence, capacity, threshold):
    """
    Graph-based greedy packing for a given station capacity, with no limit on the number of stations.
    Applies the same selection rule as the fixed-target procedure: the first available task that fits
    is assigned; otherwise the lowest-weight task is assigned if it fits within the threshold;
    otherwise the station closes.

    :param weights: dict of task_id -> load used for packing (RA-adjusted time or metabolic cost).
    :param tasks: dict of task_id -> time stored in the workstation.
    :param metabolic_costs: dict of task_id -> metabolic cost.
    :param precedence: A list of tuples representing precedence constraints.
    :param capacity: Station capacity in the units of weights.
    :param threshold: Percentage of the capacity a station may be exceeded by.
    :return: A dictionary of workstation ID -> Workstation, or None if a single task exceeds the capacity.
    """
    Workstation.reset_idx()
    graph = Graph(precedence, weights, metabolic_costs)
    workstations = {1: Workstation()}
    workstation = workstations[1]
    load = 0
    while graph.available_tasks:
        task_to_assign = None
        for task in graph.available_tasks:
            if load + weights[task] <= capacity:
                task_to_assign = task
                break
        if task_to_assign is None:
            lowest = min(graph.available_tasks, key=lambda t: weights[t])
            if load + weights[lowest] <= capacity * (1 + threshold / 100):
                task_to_assign = lowest

        if task_to_assign is not None:
            workstation.add_task(task_to_assign, tasks[task_to_assign], metabolic_costs[task_to_assign])
            load += weights[task_to_assign]
            graph.remove_task(task_to_assign)
        elif not workstation.tasks:
            return None
        else:
            workstation = Workstation()
            workstations[workstation.id] = workstation
            load = 0
    return workstations

def search_capacity(weights, tasks, metabolic_costs, precedence, target, threshold, n_operators, tol=1e-4):
    """
    Finds, by bisection, the smallest station capacity for which the greedy packing uses at most
    n_operators workstations, starting from the target load (sum of weights / K).

    :param weights: dict of task_id -> load used for packing (RA-adjusted time or metabolic cost).
    :param target: Target load per workstation (lower bound of the search).
    :return: A dictionary of workstation ID -> Workstation.
    """
    lo = max(target, max(weights.values()) / (1 + threshold / 100))
    workstations = pack_workstations(weights, tasks, metabolic_costs, precedence, lo, threshold)
    if workstations is not None and len(workstations) <= n_operators:
        return workstations
    hi = sum(weights.values())
    best = pack_workstations(weights, tasks, metabolic_costs, precedence, hi, threshold)
    while hi - lo > tol * lo:
        mid = (lo + hi) / 2
        workstations = pack_workstations(weights, tasks, metabolic_costs, precedence, mid, threshold)
        if workstations is not None and len(workstations) <= n_operators:
            hi, best = mid, workstations
        else:
            lo = mid
    return best


def distribution_considering_both(tasks, metabolic_costs, precedence, cycle_time, max_metabolic_cost, threshold, n_operators, alpha=0.5, capacity_search=True, local_search=True):
    """
    Solve with both cycle time and metabolic cost constraints.

    :param tasks: A dictionary where keys are task IDs, and values are processing times.
    :param metabolic_costs: A dictionary where keys are task IDs, and values are metabolic costs.
    :param precedence: A list of tuples representing precedence constraints.
    :param cycle_time: The maximum time allowed per workstation.
    :param max_metabolic_cost: The maximum metabolic cost allowed per workstation.
    :param threshold: The threshold for the percentage of additional task effort to be added.
    :param n_operators: The number of operators available.
    :param alpha: Weight for cycle time in conflict resolution (0=metabolic only, 1=time only, default 0.5).
    :param capacity_search: If True, the single-objective solutions use the capacity search; if False, the fixed target.
    :param local_search: If True, the consensus, TIME and METABOLIC_COST solutions are improved by local_search_balance
                         and the best is returned; if False, the consensus solution is returned.
    :return: A dictionary where keys are workstation IDs, and values are lists of task IDs assigned to each workstation.
    """
    dbt = distribution_based_on_time(tasks, metabolic_costs, precedence, cycle_time, threshold, n_operators, capacity_search=capacity_search, local_search=local_search)
    Workstation.reset_idx()
    dbmc = distribution_based_on_metabolic_cost(tasks, metabolic_costs, precedence, max_metabolic_cost, threshold, n_operators, capacity_search=capacity_search, local_search=local_search)
    Workstation.reset_idx()
    # one workstation per station id of the single-objective solutions, so that conflict tasks
    # can be placed in any candidate station even when it holds no consensus task
    workstations = {}
    for ws_id in sorted(set(dbt) | set(dbmc)):
        w = Workstation()
        w.id = ws_id
        workstations[ws_id] = w

    missing_assignments = []
    for ws_id in dbt:
        for task in dbt[ws_id].get_tasks():
            if ws_id in dbmc and task in dbmc[ws_id].get_tasks():
                workstations[ws_id].add_task(task, tasks[task], metabolic_costs[task])
            else:
                missing_assignments.append(task)

    # Assign missing tasks to the best workstation, in topological order, among the candidate
    # workstations that are not earlier than the workstations of the task's assigned predecessors
    adjusted_times = compute_per_task_ra_times(tasks, metabolic_costs)
    predecessors = defaultdict(list)
    for a, b in precedence:
        predecessors[b].append(a)
    station_of = {t: ws_id for ws_id, ws in workstations.items() for t in ws.get_tasks()}
    topological_index = {t: i for i, t in enumerate(topological_order(tasks, precedence))}
    missing_assignments.sort(key=lambda t: topological_index[t])
    for task in missing_assignments:
        earliest = max((station_of[p] for p in predecessors[task] if p in station_of), default=1)
        best_workstation = None
        workstations_with_task = []
        for ws_id, workstation in dbt.items():
            if task in workstation.get_tasks():
                workstations_with_task.append(workstation)
        for ws_id, workstation in dbmc.items():
            if task in workstation.get_tasks():
                workstations_with_task.append(workstation)

        increase_percentages = {}
        for ws in workstations_with_task:
            if ws.id < earliest:
                continue
            # RA-adjusted cycle time C' of the task and of the station (Eq. conflict)
            current_time = sum(adjusted_times[t] for t in ws.get_tasks())
            current_metabolic_cost = ws.metabolic_cost

            time_increase_percentage = ((current_time + adjusted_times[task]) / current_time - 1) * 100
            metabolic_increase_percentage = ((current_metabolic_cost + metabolic_costs[task]) / current_metabolic_cost - 1) * 100
            increase_percentages[ws.id] = [time_increase_percentage, metabolic_increase_percentage]

        # Pick the workstation with the highest combined load increase (= currently least loaded overall),
        # weighted by alpha (time) and 1-alpha (metabolic cost) to balance both objectives.
        # If no candidate respects precedence, the task goes to the earliest feasible workstation.
        if increase_percentages:
            best_workstation = max(
                increase_percentages,
                key=lambda x: alpha * increase_percentages[x][0] + (1 - alpha) * increase_percentages[x][1]
            )
        else:
            best_workstation = earliest
        workstations[best_workstation].add_task(task, tasks[task], metabolic_costs[task])
        station_of[task] = best_workstation

    if not local_search:
        return workstations

    # Stage 3: improve the consensus and both single-objective solutions by local search; keep the best
    starts = [{k: list(ws.get_tasks()) for k, ws in solution.items()} for solution in (workstations, dbt, dbmc)]
    best_score, best_station_of = None, None
    for start in starts:
        station_of = {t: k for k, ts in start.items() for t in ts}
        if not is_precedence_feasible(station_of, precedence):
            continue
        station_of, score = local_search_balance(station_of, adjusted_times, metabolic_costs, precedence, n_operators, alpha)
        if best_score is None or score < best_score:
            best_score, best_station_of = score, station_of

    Workstation.reset_idx()
    improved = {}
    for k in range(1, n_operators + 1):
        w = Workstation()
        improved[w.id] = w
    for t in sorted(best_station_of, key=lambda t: best_station_of[t]):
        improved[best_station_of[t]].add_task(t, tasks[t], metabolic_costs[t])
    return improved


def improve_workstations(workstations, stored_times, adjusted_times, metabolic_costs, precedence, n_operators, alpha):
    """
    Applies local_search_balance to a greedy solution and rebuilds the workstations.

    :param workstations: A dictionary of workstation ID -> Workstation (precedence-feasible).
    :param stored_times: dict of task_id -> time stored in the rebuilt workstations.
    :param alpha: 1 for TIME, 0 for METABOLIC_COST.
    :return: A dictionary of workstation ID -> Workstation with n_operators workstations.
    """
    station_of = {t: k for k, ws in workstations.items() for t in ws.get_tasks()}
    station_of, _ = local_search_balance(station_of, adjusted_times, metabolic_costs, precedence, n_operators, alpha)
    Workstation.reset_idx()
    improved = {}
    for k in range(1, n_operators + 1):
        w = Workstation()
        improved[w.id] = w
    for t in sorted(station_of, key=lambda t: station_of[t]):
        improved[station_of[t]].add_task(t, stored_times[t], metabolic_costs[t])
    return improved


def local_search_balance(station_of, adjusted_times, metabolic_costs, precedence, n_operators, alpha=0.5):
    """
    Local search used by all modes (alpha=1 for TIME, alpha=0 for METABOLIC_COST). Minimises, lexicographically,
      (1) alpha * max_k C_k / CT_target + (1 - alpha) * max_k M_k / MC_target
      (2) alpha * sum_k (C_k / CT_target)^2 + (1 - alpha) * sum_k (M_k / MC_target)^2
    over precedence-feasible moves of one task to another station and swaps of two tasks,
    accepting the best improving move until none exists.

    :param station_of: dict of task_id -> station (1..n_operators); the starting solution.
    :param adjusted_times: dict of task_id -> RA-adjusted time.
    :param metabolic_costs: dict of task_id -> metabolic cost.
    :param precedence: A list of tuples representing precedence constraints.
    :return: A tuple (station_of, score) with the improved assignment and its objective.
    """
    K = n_operators
    ct_target = sum(adjusted_times.values()) / K
    mc_target = sum(metabolic_costs.values()) / K
    c = {t: adjusted_times[t] / ct_target for t in adjusted_times}
    m = {t: metabolic_costs[t] / mc_target for t in metabolic_costs}
    predecessors, successors = defaultdict(list), defaultdict(list)
    for a, b in precedence:
        successors[a].append(b)
        predecessors[b].append(a)

    station_of = dict(station_of)
    load_c, load_m = [0.0] * (K + 1), [0.0] * (K + 1)
    for t, k in station_of.items():
        load_c[k] += c[t]
        load_m[k] += m[t]

    def score(lc, lm):
        return (round(alpha * max(lc[1:]) + (1 - alpha) * max(lm[1:]), 9),
                alpha * sum(x * x for x in lc[1:]) + (1 - alpha) * sum(x * x for x in lm[1:]))

    def window(t, ignore=None):
        earliest = max((station_of[p] for p in predecessors[t] if p != ignore), default=1)
        latest = min((station_of[s] for s in successors[t] if s != ignore), default=K)
        return earliest, latest

    current = score(load_c, load_m)
    tasks = list(station_of)
    while True:
        best_move, best = None, current
        # shift one task
        for t in tasks:
            p = station_of[t]
            earliest, latest = window(t)
            for q in range(earliest, latest + 1):
                if q == p:
                    continue
                lc, lm = load_c[:], load_m[:]
                lc[p] -= c[t]; lm[p] -= m[t]
                lc[q] += c[t]; lm[q] += m[t]
                s = score(lc, lm)
                if s < best:
                    best, best_move = s, ((t, q),)
        # swap two tasks in different stations
        for i, a in enumerate(tasks):
            p = station_of[a]
            for b in tasks[i + 1:]:
                q = station_of[b]
                if p == q:
                    continue
                ea, la = window(a, ignore=b)
                eb, lb = window(b, ignore=a)
                if not (ea <= q <= la and eb <= p <= lb):
                    continue
                # tasks linked by a direct arc are not swapped
                if b in successors[a] or a in successors[b]:
                    continue
                lc, lm = load_c[:], load_m[:]
                lc[p] += c[b] - c[a]; lm[p] += m[b] - m[a]
                lc[q] += c[a] - c[b]; lm[q] += m[a] - m[b]
                s = score(lc, lm)
                if s < best:
                    best, best_move = s, ((a, q), (b, p))
        if best_move is None:
            return station_of, current
        for t, q in best_move:
            p = station_of[t]
            load_c[p] -= c[t]; load_m[p] -= m[t]
            load_c[q] += c[t]; load_m[q] += m[t]
            station_of[t] = q
        current = best

   

def distribution_based_on_time(tasks, metabolic_costs, precedence, cycle_time, threshold, n_operators, use_ra=True, capacity_search=True, local_search=True):
    """
    Solve with cycle time constraint.

    :param tasks: A dictionary where keys are task IDs, and values are processing times.
    :param metabolic_costs: A dictionary where keys are task IDs, and values are metabolic costs.
    :param precedence: A list of tuples representing precedence constraints.
    :param cycle_time: The maximum time allowed per workstation.
    :param threshold: The threshold for the percentage of additional task effort to be added.
    :param capacity_search: If True, the station capacity is the smallest value >= cycle_time for which the greedy
                            uses at most n_operators workstations; if False, cycle_time is used as a fixed target
                            and the last workstation absorbs the remaining tasks.
    :param local_search: If True (with capacity_search), the greedy solution is improved by local_search_balance.
    :return: A dictionary where keys are workstation IDs, and values are lists of task IDs assigned to each workstation.
    """
    # Pre-compute RA-adjusted times per task (Method 2, Finco 2018 / Price 1990)
    adjusted_times = compute_per_task_ra_times(tasks, metabolic_costs) if use_ra else tasks

    if capacity_search:
        workstations = search_capacity(adjusted_times, adjusted_times, metabolic_costs, precedence, cycle_time, threshold, n_operators)
        if local_search:
            workstations = improve_workstations(workstations, adjusted_times, adjusted_times, metabolic_costs, precedence, n_operators, alpha=1.0)
        return workstations

    # Step 1: Build the precedence graph using adjusted times for task selection priority
    graph = Graph(precedence, adjusted_times, metabolic_costs)
    workstations = {1: Workstation()}
    workstation = workstations[1]

    assign_one_more_task = True
    while graph.available_tasks:
        current_time = workstation.cycle_time
        task_to_assign = None
        for task in graph.available_tasks:
            if current_time + adjusted_times[task] <= cycle_time:
                task_to_assign = task
                break
            elif current_time + adjusted_times[task] <= cycle_time + (threshold/100 * cycle_time):
                assign_one_more_task = True
                break
            elif workstation.id == n_operators:
                assign_one_more_task = True
                break

        if task_to_assign is None and assign_one_more_task:
            assign_one_more_task = False
            task_to_assign = graph.get_lowest_time_task()

        if task_to_assign:
            workstation.add_task(task_to_assign, adjusted_times[task_to_assign], metabolic_costs[task_to_assign])
            graph.remove_task(task_to_assign)
        else:
            # Move to the next workstation
            workstation = Workstation()
            workstations[workstation.id] = workstation

    return workstations

def distribution_based_on_metabolic_cost(tasks, metabolic_costs, precedence, max_metabolic_cost, threshold, n_operators, capacity_search=True, local_search=True):
    """
    Solve with metabolic cost constraint.

    :param tasks: A dictionary where keys are task IDs, and values are processing times.
    :param metabolic_costs: A dictionary where keys are task IDs, and values are metabolic costs.
    :param precedence: A list of tuples representing precedence constraints.
    :param max_metabolic_cost: The maximum metabolic cost allowed per workstation.
    :param threshold: The threshold for the percentage of additional task effort to be added.
    :param capacity_search: If True, the station capacity is searched as in distribution_based_on_time.
    :param local_search: If True (with capacity_search), the greedy solution is improved by local_search_balance.
    :return: A dictionary where keys are workstation IDs, and values are lists of task IDs assigned to each workstation.
    """
    if capacity_search:
        workstations = search_capacity(metabolic_costs, tasks, metabolic_costs, precedence, max_metabolic_cost, threshold, n_operators)
        if local_search:
            workstations = improve_workstations(workstations, tasks, tasks, metabolic_costs, precedence, n_operators, alpha=0.0)
        return workstations

    # Step 1: Build the precedence graph
    graph = Graph(precedence, tasks, metabolic_costs)
    workstations = {1: Workstation()}
    workstation = workstations[1]
    
    assign_one_more_task = True
    while graph.available_tasks:
        current_metabolic_cost = workstation.metabolic_cost
        task_to_assign = None
        for task in graph.available_tasks:
            if (current_metabolic_cost + metabolic_costs[task] <= max_metabolic_cost):
                task_to_assign = task
                break
            elif current_metabolic_cost + metabolic_costs[task] <= max_metabolic_cost + (threshold/100 * max_metabolic_cost):
                assign_one_more_task = True
                break
            elif workstation.id == n_operators:
                assign_one_more_task = True
                break

        if task_to_assign is None and assign_one_more_task:
            assign_one_more_task = False
            task_to_assign = graph.get_lowest_metabolic_cost_task()
        
        if task_to_assign:
            workstation.add_task(task_to_assign, tasks[task_to_assign], metabolic_costs[task_to_assign])
            graph.remove_task(task_to_assign)
        else:
            # Move to the next workstation
            workstation = Workstation()
            workstations[workstation.id] = workstation
            
    return workstations

def plot_results(data, time_objective, metabolic_cost_objective):
    """
    Plots the results of the distribution of tasks to workstations.

    :param data: A dictionary where keys are workstation IDs, and values are tuples containing the cycle time and metabolic cost.
    :param time_objective: The objective value for the cycle time.
    :param metabolic_cost_objective: The objective value for the metabolic cost.
    """
    # Extracting keys and values
    keys = list(data.keys())
    values1 = [v[0] for v in data.values()]
    values2 = [v[1] for v in data.values()]

    print(keys)
    print(values1)
    print(values2)

    # Plotting
    plt.figure(figsize=(16, 6))
    plt.bar(keys, values1, width=0.4, label='Cycle time', align='center')
    plt.bar(keys, values2, width=0.4, label='Metabolic cost', align='edge')

    # Adding objective lines
    plt.axhline(y=time_objective, color='r', linestyle='--', label='Takt time')
    plt.axhline(y=metabolic_cost_objective, color='g', linestyle='--', label='Metabolic Cost Objective')

    # Adding labels and title
    plt.xlabel('Number of operators')
    plt.ylabel('Values')
    plt.title('Performance distribution by operator')
    plt.legend()

    # Display the plot
    plt.show()