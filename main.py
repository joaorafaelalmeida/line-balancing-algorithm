import argparse
from genetic_algorithm import *

def main():
    parser = argparse.ArgumentParser(description='Genetic algorithm for line balancing.')
    parser.add_argument('data_dir', type=str, help='The file for station data.')
    parser.add_argument('precedence_diagram', type=str, help='The file for precedence diagram.')
    parser.add_argument('n_operators', type=int, help='Number of operators available.')
    parser.add_argument('distribution_type', type=str, help='Distribution type: [TIME, METABOLIC_COST, BOTH]')
    parser.add_argument('--threshold', type=int, help='Percentage of additional task effort to be added.', default=10)
    args = parser.parse_args()

    data_file = args.data_dir
    precedence_file = args.precedence_diagram
    n_operators = args.n_operators
    threshold = args.threshold

    # Read data from files
    tasks, metabolic_costs = read_data_file(data_file)
    precedence = read_precedence_file(precedence_file)
    cycle_time = calculate_avg_cycle_time(tasks, n_operators)
    max_metabolic_cost = calculate_avg_metabolic_cost(metabolic_costs, n_operators)
    print(f"Cycle time: {cycle_time} and metabolic cost: {max_metabolic_cost}")
  
    # Distribution of tasks
    if args.distribution_type == 'TIME':
        results = distribution_based_on_time(tasks, metabolic_costs, precedence, cycle_time, threshold, n_operators)
    elif args.distribution_type == 'METABOLIC_COST':
        results = distribution_based_on_metabolic_cost(tasks, metabolic_costs, precedence, max_metabolic_cost, threshold, n_operators)
    elif args.distribution_type == 'BOTH':
        results = distribution_considering_both(tasks, metabolic_costs, precedence, cycle_time, max_metabolic_cost, threshold, n_operators)

    workstations_performance = Workstation.get_overall_performance(results)
    plot_results(workstations_performance, cycle_time, max_metabolic_cost)

if __name__ == "__main__":
    main()

