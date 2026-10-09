import argparse
import algorithm
from algorithm import *

def main():
    parser = argparse.ArgumentParser(description='Graph-based greedy heuristic for assembly line balancing with rest allowance.')
    parser.add_argument('data_dir', type=str, help='The file for station data.')
    parser.add_argument('precedence_diagram', type=str, help='The file for precedence diagram.')
    parser.add_argument('n_operators', type=int, help='Number of operators available.')
    parser.add_argument('distribution_type', type=str, help='Distribution type: [TIME, METABOLIC_COST, BOTH]')
    parser.add_argument('--threshold', type=int,   help='Percentage of additional task effort to be added.', default=0)
    parser.add_argument('--alpha',     type=float, help='Weight for cycle time in BOTH mode (0–1, default 0.5).', default=0.5)
    parser.add_argument('--mawl',      type=float, help='Maximum Acceptable Working Level in kCal/min (default 3.5).', default=algorithm.MAWL)
    args = parser.parse_args()

    algorithm.MAWL = args.mawl
    n_operators = args.n_operators
    threshold = args.threshold

    # Read data from files
    tasks, metabolic_costs = read_data_file(args.data_dir)
    precedence = read_precedence_file(args.precedence_diagram)
    adjusted_times = compute_per_task_ra_times(tasks, metabolic_costs)
    cycle_time = calculate_avg_cycle_time(adjusted_times, n_operators)
    max_metabolic_cost = calculate_avg_metabolic_cost(metabolic_costs, n_operators)
    print(f"RA-adjusted cycle time target: {cycle_time:.1f} s and metabolic cost target: {max_metabolic_cost:.2f} kCal")

    # Distribution of tasks
    if args.distribution_type == 'TIME':
        results = distribution_based_on_time(tasks, metabolic_costs, precedence, cycle_time, threshold, n_operators)
    elif args.distribution_type == 'METABOLIC_COST':
        results = distribution_based_on_metabolic_cost(tasks, metabolic_costs, precedence, max_metabolic_cost, threshold, n_operators)
    elif args.distribution_type == 'BOTH':
        results = distribution_considering_both(tasks, metabolic_costs, precedence, cycle_time, max_metabolic_cost, threshold, n_operators, alpha=args.alpha)
    else:
        parser.error('distribution_type must be TIME, METABOLIC_COST or BOTH')

    # Station loads on the same basis for all modes: RA-adjusted time and metabolic cost
    workstations_performance = {
        ws_id: (sum(adjusted_times[t] for t in ws.get_tasks()), sum(metabolic_costs[t] for t in ws.get_tasks()))
        for ws_id, ws in results.items()
    }
    plot_results(workstations_performance, cycle_time, max_metabolic_cost)

if __name__ == "__main__":
    main()
