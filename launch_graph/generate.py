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
import tempfile

from launch import LaunchContext, LaunchDescription
from launch.actions import IncludeLaunchDescription, GroupAction
from launch_ros.actions import Node


def resolve_substitutions(subst, context):
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
    spec = importlib.util.spec_from_file_location('launch_module', path)
    launch_module = importlib.util.module_from_spec(spec)
    sys.modules['launch_module'] = launch_module
    spec.loader.exec_module(launch_module)

    if not hasattr(launch_module, 'generate_launch_description'):
        raise AttributeError(f'{path} does not define generate_launch_description()')

    return launch_module.generate_launch_description()

def print_launch_tree(ld: LaunchDescription, indent=0, context=None):
    if context is None:
        context = LaunchContext()
    for action in ld.entities:
        print_action_tree(action, indent, context)


def print_action_tree(action, indent, context):
    prefix = '  ' * indent

    if isinstance(action, IncludeLaunchDescription):
        filename = '<unknown>'
        try:
            source = action.launch_description_source
            if hasattr(source, 'launch_file_path'):
                path_str = source.launch_file_path
            elif hasattr(source, 'launch_file_path_substitutions'):
                path_str = resolve_substitutions(source.launch_file_path_substitutions, context)
            elif hasattr(source, 'location'):
                path_str = str(source.location)
            elif hasattr(source, 'perform'):
                path_str = source.perform(context)
            else:
                path_str = str(source)
            filename = os.path.basename(path_str)
        except Exception as e:
            filename = f'<error: {e}>'

        print(prefix + f'Include: {filename}')

        try:
            nested_ld = source.get_launch_description(context)
            if isinstance(nested_ld, LaunchDescription):
                print_launch_tree(nested_ld, indent + 1, context)
            else:
                print(prefix + f'(Unexpected return type: {type(nested_ld).__name__})')
        except Exception as e:
            print(prefix + f'(Could not load: {e})')

    elif isinstance(action, Node):
        try:
            raw_exe = getattr(action, 'node_executable', '<missing>')
            exe = resolve_substitutions(raw_exe, context)
            print(prefix + f'Node: {exe}')
        except Exception as e:
            print(prefix + f'Node: <missing> (error: {e})')

    elif isinstance(action, GroupAction):
        print(prefix + 'Group:')
        try:
            for sub_action in action.get_sub_entities():
                print_action_tree(sub_action, indent + 1, context)
        except Exception as e:
            print(prefix + f'(Could not evaluate group: {e})')


def collect_edges(ld, parent, context=None, edges=None, node_shapes=None):
    if context is None:
        context = LaunchContext()
    if edges is None:
        edges = set()
    if node_shapes is None:
        node_shapes = {}

    node_shapes[parent] = 'box'

    for action in ld.entities:
        collect_action_edges(action, parent, context, edges, node_shapes)

    return edges, node_shapes


def collect_action_edges(action, parent, context, edges, node_shapes):
    if isinstance(action, IncludeLaunchDescription):
        try:
            source = action.launch_description_source
            if hasattr(source, 'launch_file_path'):
                path_str = source.launch_file_path
            elif hasattr(source, 'launch_file_path_substitutions'):
                path_str = resolve_substitutions(source.launch_file_path_substitutions, context)
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
            pass

    elif isinstance(action, Node):
        try:
            raw_exe = getattr(action, 'node_executable', '<missing>')
            exe = resolve_substitutions(raw_exe, context)
            edges.add((parent, exe))
            node_shapes[exe] = 'ellipse'
        except Exception:
            pass

    elif isinstance(action, GroupAction):
        try:
            for sub_action in action.get_sub_entities():
                collect_action_edges(sub_action, parent, context, edges, node_shapes)
        except Exception:
            pass


def generate_dot_content(edges, node_shapes):
    lines = []
    lines.append('digraph LaunchTree {')
    lines.append('  node [fontname="Arial"];')
    lines.append('  rankdir=TB;')
    for node, shape in node_shapes.items():
        lines.append(f'  "{node}" [shape={shape}];')
    for parent, child in sorted(edges):
        lines.append(f'  "{parent}" -> "{child}";')
    lines.append('}')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Generate a graph from a ROS 2 launch file.'
    )
    parser.add_argument(
        'launch_file', help='Path to the ROS 2 launch file (.py) to inspect'
    )
    parser.add_argument(
        '--out',
        help='Output file name (defaults to launch_tree.<format>)',
    )
    parser.add_argument(
        '--format',
        choices=['png', 'pdf', 'dot'],
        default='png',
        help='Output format (default: png)',
    )

    args = parser.parse_args()

    if not args.out:
        args.out = f'launch_tree.{args.format}'

    if not os.path.exists(args.launch_file):
        print(f'Error: file does not exist: {args.launch_file}')
        sys.exit(1)

    try:
        ld = load_launch_description_from_file(args.launch_file)
        root = os.path.basename(args.launch_file)

        print(f'Launch Tree for {args.launch_file}:\n')
        print_launch_tree(ld)

        edges, node_shapes = collect_edges(ld, parent=root)
        dot_content = generate_dot_content(edges, node_shapes)

        if args.format == 'dot':
            with open(args.out, 'w') as f:
                f.write(dot_content)
            print(f'DOT graph written to: {args.out}')
        else:
            with tempfile.NamedTemporaryFile('w', suffix='.dot', delete=False) as f:
                f.write(dot_content)
                tmp_dot_path = f.name

            try:
                subprocess.run(['dot', f'-T{args.format}', tmp_dot_path, '-o', args.out],
                               check=True)
                print(f'{args.format.upper()} generated at: {args.out}')
            except Exception as e:
                print(f'Failed to generate {args.format.upper()}: {e}')
            finally:
                os.remove(tmp_dot_path)

    except Exception as e:
        print(f'Error loading launch file: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
