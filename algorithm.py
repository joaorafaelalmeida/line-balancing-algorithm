from collections import defaultdict
import matplotlib.pyplot as plt

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

def distribution_considering_both(tasks, metabolic_costs, precedence, cycle_time, max_metabolic_cost, threshold, n_operators):
    """
    Solve with both cycle time and metabolic cost constraints.

    :param tasks: A dictionary where keys are task IDs, and values are processing times.
    :param metabolic_costs: A dictionary where keys are task IDs, and values are metabolic costs.
    :param precedence: A list of tuples representing precedence constraints.
    :param cycle_time: The maximum time allowed per workstation.
    :param max_metabolic_cost: The maximum metabolic cost allowed per workstation.
    :param threshold: The threshold for the percentage of additional task effort to be added.
    :param n_operators: The number of operators available.
    :return: A dictionary where keys are workstation IDs, and values are lists of task IDs assigned to each workstation.
    """
    dbt = distribution_based_on_time(tasks, metabolic_costs, precedence, cycle_time, threshold, n_operators)
    Workstation.reset_idx()
    dbmc = distribution_based_on_metabolic_cost(tasks, metabolic_costs, precedence, max_metabolic_cost, threshold, n_operators)
    Workstation.reset_idx()
    workstations = {}

    missing_assignments = []
    for ws_id in dbt:
        if ws_id in dbmc:
            for task in dbt[ws_id].get_tasks():
                if task in dbmc[ws_id].get_tasks():
                    if ws_id not in workstations:
                        w = Workstation()
                        workstations[w.id] = w
                    workstations[w.id].add_task(task, tasks[task], metabolic_costs[task])
                else:
                    missing_assignments.append(task)

    # Assign missing tasks to the best workstation
    for task in missing_assignments:
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
            current_time = ws.cycle_time
            current_metabolic_cost = ws.metabolic_cost

            time_increase_percentage = ((current_time + tasks[task]) / current_time - 1) * 100
            metabolic_increase_percentage = ((current_metabolic_cost + metabolic_costs[task]) / current_metabolic_cost - 1) * 100
            increase_percentages[ws.id] = [time_increase_percentage, metabolic_increase_percentage]

        best_workstation = max(increase_percentages, key=lambda x: increase_percentages[x][0])
        if best_workstation:
            workstations[best_workstation].add_task(task, tasks[task], metabolic_costs[task])

    return workstations

   

def distribution_based_on_time(tasks, metabolic_costs, precedence, cycle_time, threshold, n_operators):
    """
    Solve with cycle time constraint.
    
    :param tasks: A dictionary where keys are task IDs, and values are processing times.
    :param metabolic_costs: A dictionary where keys are task IDs, and values are metabolic costs.
    :param precedence: A list of tuples representing precedence constraints.
    :param cycle_time: The maximum time allowed per workstation.
    :param threshold: The threshold for the percentage of additional task effort to be added.
    :return: A dictionary where keys are workstation IDs, and values are lists of task IDs assigned to each workstation.
    """
    # Step 1: Build the precedence graph
    graph = Graph(precedence, tasks, metabolic_costs)
    workstations = {1: Workstation()}
    workstation = workstations[1]
    
    assign_one_more_task = True
    while graph.available_tasks:
        current_time = workstation.cycle_time
        task_to_assign = None
        for task in graph.available_tasks:
            if (current_time + tasks[task] <= cycle_time):
                task_to_assign = task
                break
            elif current_time + tasks[task] <= cycle_time + (threshold/100 * cycle_time):
                assign_one_more_task = True
                break
            elif workstation.id == n_operators:
                assign_one_more_task = True
                break

        if task_to_assign is None and assign_one_more_task:
            assign_one_more_task = False
            task_to_assign = graph.get_lowest_time_task()
        
        if task_to_assign:
            workstation.add_task(task_to_assign, tasks[task_to_assign], metabolic_costs[task_to_assign])
            graph.remove_task(task_to_assign)
        else:
            # Move to the next workstation
            workstation = Workstation()
            workstations[workstation.id] = workstation
            
    return workstations

def distribution_based_on_metabolic_cost(tasks, metabolic_costs, precedence, max_metabolic_cost, threshold, n_operators):
    """
    Solve with metabolic cost constraint.
    
    :param tasks: A dictionary where keys are task IDs, and values are processing times.
    :param metabolic_costs: A dictionary where keys are task IDs, and values are metabolic costs.
    :param precedence: A list of tuples representing precedence constraints.
    :param max_metabolic_cost: The maximum metabolic cost allowed per workstation.
    :param threshold: The threshold for the percentage of additional task effort to be added.
    :return: A dictionary where keys are workstation IDs, and values are lists of task IDs assigned to each workstation.
    """
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