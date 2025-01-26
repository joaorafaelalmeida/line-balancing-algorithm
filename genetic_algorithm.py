from collections import defaultdict
import matplotlib.pyplot as plt

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


def result_with_metabolic_cost(tasks, metabolic_costs, precedence, cycle_time, max_metabolic_cost):
    """
    Solve with both cycle time and metabolic cost constraints.
    
    :param tasks: A dictionary where keys are task IDs, and values are processing times.
    :param metabolic_costs: A dictionary where keys are task IDs, and values are metabolic costs.
    :param precedence: A list of tuples representing precedence constraints.
    :param cycle_time: The maximum time allowed per workstation.
    :param max_metabolic_cost: The maximum metabolic cost allowed per workstation.
    :return: A dictionary where keys are workstation IDs, and values are lists of task IDs assigned to each workstation.
    """
    # Step 1: Build the precedence graph
    task_graph = defaultdict(list)
    indegree = defaultdict(int)
    for a, b in precedence:
        task_graph[a].append(b)
        indegree[b] += 1
        if a not in indegree:
            indegree[a] = 0
    
    # Step 2: Find tasks with no prerequisites (indegree 0)
    available_tasks = [task for task in tasks if indegree[task] == 0]
    
    # Step 3: Assign tasks to workstations
    workstations = defaultdict(list)
    workstations_performance = defaultdict(tuple)
    workstation_id = 1
    current_time = 0
    current_metabolic_cost = 0
    
    assign_one_more_task = True
    while available_tasks:
        task_to_assign = None
        for task in available_tasks:
            if (current_time + tasks[task] <= cycle_time and
                current_metabolic_cost + metabolic_costs[task] <= max_metabolic_cost):
                task_to_assign = task
                assign_one_more_task = True
                break

        if task_to_assign is None and assign_one_more_task:
            assign_one_more_task = False
            task_to_assign = available_tasks[0]
            # Discover if it was a time problem or metabolic cost problem
            if current_time + tasks[available_tasks[0]] > cycle_time:
                # It was a time problem
                for task in available_tasks:
                    if tasks[task] < tasks[task_to_assign]:
                        task_to_assign = task
            else:
                # It was a metabolic cost problem
                for task in available_tasks:
                    if metabolic_costs[task] < metabolic_costs[task_to_assign]:
                        task_to_assign = task
        
        if task_to_assign:
            # Assign task to the current workstation
            workstations[workstation_id].append(task_to_assign)
            current_time += tasks[task_to_assign]
            current_metabolic_cost += metabolic_costs[task_to_assign]
            available_tasks.remove(task_to_assign)
            
            # Update indegree of dependent tasks
            for dependent_task in task_graph[task_to_assign]:
                indegree[dependent_task] -= 1
                if indegree[dependent_task] == 0:
                    available_tasks.append(dependent_task)
        else:
            workstations_performance[workstation_id] = (current_time, current_metabolic_cost)
            # Move to the next workstation
            workstation_id += 1
            current_time = 0
            current_metabolic_cost = 0
    
    workstations_performance[workstation_id] = (current_time, current_metabolic_cost)
    return dict(workstations), dict(workstations_performance)

def plot_results(data, time_objective, metabolic_cost_objective):
    # Extracting keys and values
    keys = list(data.keys())
    values1 = [v[0] for v in data.values()]
    values2 = [v[1] for v in data.values()]

    # Plotting
    plt.figure(figsize=(10, 6))
    plt.bar(keys, values1, width=0.4, label='Cycle time', align='center')
    plt.bar(keys, values2, width=0.4, label='Metabolic cost', align='edge')

    # Adding objective lines
    plt.axhline(y=time_objective, color='r', linestyle='--', label='Time Objective')
    plt.axhline(y=metabolic_cost_objective, color='g', linestyle='--', label='Metabolic Cost Objective')

    # Adding labels and title
    plt.xlabel('Key')
    plt.ylabel('Values')
    plt.title('Bar Chart of Data')
    plt.legend()

    # Display the plot
    plt.show()