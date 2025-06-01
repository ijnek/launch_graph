#!/usr/bin/env python3
# Copyright (c) 2025 Kenji Brameld
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import importlib.util
import os
import subprocess
import sys

from launch import LaunchContext, LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch_ros.actions import Node


def resolve_substitutions(subst, context):
    """Resolve substitutions or lists of substitutions in launch files."""
    try:
        if isinstance(subst, list):
            return ''.join(
                s.perform(context) if hasattr(s, 'perform') else str(s) for s in subst
            )
        elif hasattr(subst, 'perform'):
            return subst.perform(context)
        else:
            return str(subst)
    except Exception as e:
        return f'<could not resolve: {e}>'


def load_launch_description_from_file(path):
    """Load the LaunchDescription from a given launch file path."""
    spec = importlib.util.spec_from_file_location('launch_module', path)
    launch_module = importlib.util.module_from_spec(spec)
    sys.modules['launch_module'] = launch_module
    spec.loader.exec_module(launch_module)

    if not hasattr(launch_module, 'generate_launch_description'):
        raise AttributeError(f'{path} does not define generate_launch_description()')

    return launch_module.generate_launch_description()


def print_launch_tree(ld, indent=0, context=None):
    """Print a tree view of the launch file structure to the console."""
    if context is None:
        context = LaunchContext()

    for action in ld.entities:
        if isinstance(action, IncludeLaunchDescription):
            filename = '<unknown>'
            try:
                source = action.launch_description_source
                if hasattr(source, 'launch_file_path'):
                    path_str = source.launch_file_path
                elif hasattr(source, 'launch_file_path_substitutions'):
                    path_str = resolve_substitutions(
                        source.launch_file_path_substitutions, context
                    )
                elif hasattr(source, 'location'):
                    path_str = str(source.location)
                elif hasattr(source, 'perform'):
                    path_str = source.perform(context)
                else:
                    path_str = str(source)
                filename = os.path.basename(path_str)
            except Exception as e:
                filename = f'<error: {e}>'

            print('  ' * indent + f'Include: {filename}')

            try:
                nested_ld = source.get_launch_description(context)
                if isinstance(nested_ld, LaunchDescription):
                    print_launch_tree(nested_ld, indent + 1, context)
                else:
                    print(
                        '  ' * (indent + 1)
                        + f'(Unexpected return type: {type(nested_ld).__name__})'
                    )
            except Exception as e:
                print('  ' * (indent + 1) + f'(Could not load: {e})')

        elif isinstance(action, Node):
            try:
                raw_exe = getattr(action, 'node_executable', '<missing>')
                exe = resolve_substitutions(raw_exe, context)
                print('  ' * indent + f'Node: {exe}')
            except Exception as e:
                print('  ' * indent + f'Node: <missing> (error: {e})')


def collect_edges(ld, parent, context=None, edges=None, node_shapes=None):
    """Collect edges between launch files and nodes for graph generation."""
    if context is None:
        context = LaunchContext()
    if edges is None:
        edges = set()
    if node_shapes is None:
        node_shapes = {}

    node_shapes[parent] = 'box'

    for action in ld.entities:
        if isinstance(action, IncludeLaunchDescription):
            try:
                source = action.launch_description_source
                if hasattr(source, 'launch_file_path'):
                    path_str = source.launch_file_path
                elif hasattr(source, 'launch_file_path_substitutions'):
                    path_str = resolve_substitutions(
                        source.launch_file_path_substitutions, context
                    )
                elif hasattr(source, 'location'):
                    path_str = str(source.location)
                elif hasattr(source, 'perform'):
                    path_str = source.perform(context)
                else:
                    path_str = str(source)

                filename = os.path.basename(path_str)
                edges.add((parent, filename))
                node_shapes[filename] = 'box'

                nested_ld = source.get_launch_description(context)
                if isinstance(nested_ld, LaunchDescription):
                    collect_edges(nested_ld, filename, context, edges, node_shapes)
            except Exception:
                continue

        elif isinstance(action, Node):
            try:
                raw_exe = getattr(action, 'node_executable', '<missing>')
                exe = resolve_substitutions(raw_exe, context)
                edges.add((parent, exe))
                node_shapes[exe] = 'ellipse'
            except Exception:
                continue

    return edges, node_shapes


def write_dot(edges, node_shapes, dot_path='launch_tree.dot'):
    """Generate a DOT file representing the launch graph."""
    with open(dot_path, 'w') as f:
        f.write('digraph LaunchTree {\n')
        f.write('  node [fontname=\"Arial\"];\n')
        f.write('  rankdir=TB;\n')
        for node, shape in node_shapes.items():
            f.write(f'  "{node}" [shape={shape}];\n')
        for parent, child in sorted(edges):
            f.write(f'  "{parent}" -> "{child}";\n')
        f.write('}\n')
    print(f'\nDOT graph written to: {dot_path}')
    return dot_path


def generate_pdf(dot_path, pdf_path='launch_tree.pdf'):
    """Run Graphviz to generate a PDF from the DOT file."""
    try:
        subprocess.run(['dot', '-Tpdf', dot_path, '-o', pdf_path], check=True)
        print(f'PDF generated at: {pdf_path}')
    except Exception as e:
        print(f'Failed to generate PDF: {e}')


def main():
    parser = argparse.ArgumentParser(
        description='Generate a graph from a ROS 2 launch file.'
    )
    parser.add_argument(
        'launch_file', help='Path to the ROS 2 launch file (.py) to inspect'
    )
    parser.add_argument(
        '--dot',
        default='launch_tree.dot',
        help='Path to output DOT file (default: launch_tree.dot)',
    )
    parser.add_argument(
        '--pdf',
        default='launch_tree.pdf',
        help='Path to output PDF file (default: launch_tree.pdf)',
    )

    args = parser.parse_args()

    if not os.path.exists(args.launch_file):
        print(f'Error: file does not exist: {args.launch_file}')
        sys.exit(1)

    try:
        ld = load_launch_description_from_file(args.launch_file)
        root = os.path.basename(args.launch_file)

        print(f'Launch Tree for {args.launch_file}:\n')
        print_launch_tree(ld)

        edges, node_shapes = collect_edges(ld, parent=root)
        dot_path = write_dot(edges, node_shapes, dot_path=args.dot)
        generate_pdf(dot_path, pdf_path=args.pdf)

    except Exception as e:
        print(f'Error loading launch file: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
