# Line Balancing Algorithm

## Overview

This project implements a line balancing algorithm to optimize task assignments to workstations while considering constraints such as cycle time and precedence.

## Features

- **Precedence Constraints**: Ensures tasks are assigned in a valid order based on precedence constraints.
- **Cycle Time Optimization**: Balances tasks to minimize cycle time per workstation.

## Files

- `precedencediagram.dot`: A DOT file representing the precedence constraints between tasks.
- `.gitignore`: Specifies files and directories to be ignored by Git.

## Usage

1. **Prepare Data**: Ensure your precedence diagram is correctly formatted and available.
2. **Run the Algorithm**: Implement and execute your algorithm using the provided precedence constraints.

## Example

To visualize the precedence constraints, you can use graph visualization tools that support DOT files.

```
$ python main.py files/data.txt files/precedencediagram.dot 5
```

![Example for 5 operators.](figs/plot_for_5_operators.png) 

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License.