# 📈 launch_graph

`launch_graph` is a ROS 2 command-line tool for visualizing the structure of launch files. It recursively identifies launch file includes and node executions, and generates a visual graph.

## 🔧 Features

- Parses `IncludeLaunchDescription` and `Node` actions
- Outputs a `.dot` graph file
- Automatically generates a `.pdf` visualization using Graphviz
- Uses:
  - **Boxes** for launch files
  - **Ellipses** for nodes

## 📦 Installation

1. Clone this package into your ROS 2 workspace:
   ```bash
   git clone git@github.com:ijnek/launch_graph.git src/launch_graph
   ```

2. Build and source:
   ```bash
   colcon build --packages-select launch_graph
   source install/setup.bash
   ```

3. Ensure `graphviz` is installed:
   ```bash
   sudo apt install graphviz
   ```

## 🚀 Usage

```bash
ros2 run launch_graph generate <path_to_launch_file.py>
```

This will:

- Print a launch tree to the terminal
- Write `launch_tree.dot`
- Generate `launch_tree.pdf`

### Optional arguments

- `--dot <file.dot>`: Output path for the DOT file (default: `launch_tree.dot`)
- `--pdf <file.pdf>`: Output path for the PDF file (default: `launch_tree.pdf`)

## 🗂 Example

```bash
ros2 run launch_graph generate src/my_package/launch/my_launch.py --pdf my_graph.pdf
```

## 📝 File Structure

```
launch_graph/
├── launch_graph/
│   └── generate.py
├── setup.py
├── setup.cfg
└── package.xml
```

## 📄 License

Apache License 2.0
