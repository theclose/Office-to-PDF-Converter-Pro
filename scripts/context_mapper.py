"""
Project Context Mapper - AST-based Dependency Graph Generator
=============================================================
Creates an "architecture map" of the entire project by:
1. Parsing all Python files with AST
2. Extracting imports, classes, functions
3. Building a dependency graph
4. Grouping related files into context chunks (MVC pattern)

Usage:
    python context_mapper.py [project_path] [--output=json|md|both]
    
Output:
    - dependency_graph.json: Machine-readable dependency data
    - context_map.md: Human-readable architecture documentation
    - context_chunks/: Grouped context files for AI consumption
"""

import ast
import os
import sys
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
import re


@dataclass
class ModuleInfo:
    """Information about a Python module."""
    path: str
    package: str
    name: str
    imports: List[str] = field(default_factory=list)
    from_imports: Dict[str, List[str]] = field(default_factory=dict)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    lines: int = 0
    category: str = "other"  # model, view, controller, util, test


@dataclass
class DependencyGraph:
    """Complete project dependency information."""
    project_root: str
    modules: Dict[str, ModuleInfo] = field(default_factory=dict)
    edges: List[Tuple[str, str]] = field(default_factory=list)  # (from, to)
    clusters: Dict[str, List[str]] = field(default_factory=dict)  # category -> modules


class ASTAnalyzer(ast.NodeVisitor):
    """Analyzes Python AST to extract module information."""
    
    def __init__(self):
        self.imports = []
        self.from_imports = defaultdict(list)
        self.classes = []
        self.functions = []
        self.docstring = None
        
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            self.from_imports[module].append(alias.name)
        self.generic_visit(node)
        
    def visit_ClassDef(self, node):
        self.classes.append(node.name)
        # Don't recurse into class body for top-level analysis
        
    def visit_FunctionDef(self, node):
        # Only top-level functions
        self.functions.append(node.name)
        
    def visit_AsyncFunctionDef(self, node):
        self.functions.append(node.name)


def categorize_module(path: str, content: str) -> str:
    """Categorize module based on path and content patterns."""
    path_lower = path.lower()
    
    # Path-based categorization
    if "/tests/" in path or "\\tests\\" in path or path.endswith("_test.py"):
        return "test"
    if "/ui/" in path or "\\ui\\" in path or "_ui" in path:
        return "view"
    if "/models/" in path or "\\models\\" in path:
        return "model"
    if "/core/" in path or "\\core\\" in path:
        return "model"
    if "/converters/" in path or "\\converters\\" in path:
        return "controller"
    if "/grid/" in path or "\\grid\\" in path:
        return "controller"
    if "/utils/" in path or "\\utils\\" in path:
        return "util"
    if "/scripts/" in path or "\\scripts\\" in path:
        return "script"
        
    # Content-based fallback
    if "class " in content and ("Dialog" in content or "Window" in content or "Frame" in content):
        return "view"
    if "def convert" in content or "def process" in content:
        return "controller"
        
    return "other"


def analyze_file(file_path: str, project_root: str) -> Optional[ModuleInfo]:
    """Analyze a single Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        tree = ast.parse(content)
        analyzer = ASTAnalyzer()
        analyzer.visit(tree)
        
        # Get docstring
        docstring = ast.get_docstring(tree)
        
        # Calculate relative path
        rel_path = os.path.relpath(file_path, project_root)
        
        # Build package name
        package_parts = rel_path.replace("\\", "/").replace(".py", "").split("/")
        package = ".".join(package_parts[:-1]) if len(package_parts) > 1 else ""
        name = package_parts[-1]
        
        return ModuleInfo(
            path=rel_path,
            package=package,
            name=name,
            imports=analyzer.imports,
            from_imports=dict(analyzer.from_imports),
            classes=analyzer.classes,
            functions=analyzer.functions,
            docstring=docstring[:200] if docstring else None,
            lines=len(content.splitlines()),
            category=categorize_module(file_path, content)
        )
        
    except SyntaxError as e:
        print(f"  ⚠️ Syntax error in {file_path}: {e}")
        return None
    except Exception as e:
        print(f"  ⚠️ Error analyzing {file_path}: {e}")
        return None


def build_dependency_graph(project_root: str, exclude_patterns: List[str] = None) -> DependencyGraph:
    """Build complete dependency graph for project."""
    if exclude_patterns is None:
        exclude_patterns = ["__pycache__", ".git", "venv", ".venv", "node_modules"]
        
    graph = DependencyGraph(project_root=project_root)
    
    print(f"📂 Scanning project: {project_root}")
    
    # Find all Python files
    py_files = []
    for root, dirs, files in os.walk(project_root):
        # Filter excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_patterns]
        
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
                
    print(f"   Found {len(py_files)} Python files")
    
    # Analyze each file
    for file_path in py_files:
        info = analyze_file(file_path, project_root)
        if info:
            graph.modules[info.path] = info
            
    print(f"   Analyzed {len(graph.modules)} modules")
    
    # Build edges (dependencies)
    module_names = set()
    for path, info in graph.modules.items():
        # Create full module name
        if info.package:
            module_names.add(f"{info.package}.{info.name}")
        module_names.add(info.name)
        
    for path, info in graph.modules.items():
        source = f"{info.package}.{info.name}" if info.package else info.name
        
        # Direct imports
        for imp in info.imports:
            graph.edges.append((source, imp))
            
        # From imports
        for module, names in info.from_imports.items():
            graph.edges.append((source, module))
            
    print(f"   Built {len(graph.edges)} dependency edges")
    
    # Build clusters by category
    for path, info in graph.modules.items():
        if info.category not in graph.clusters:
            graph.clusters[info.category] = []
        graph.clusters[info.category].append(path)
        
    return graph


def generate_context_chunks(graph: DependencyGraph, output_dir: str):
    """Generate grouped context files for AI consumption."""
    chunks_dir = os.path.join(output_dir, "context_chunks")
    os.makedirs(chunks_dir, exist_ok=True)
    
    # Group by category
    for category, paths in graph.clusters.items():
        if not paths:
            continue
            
        chunk_path = os.path.join(chunks_dir, f"{category}_context.md")
        
        with open(chunk_path, 'w', encoding='utf-8') as f:
            f.write(f"# {category.upper()} Layer Context\n\n")
            f.write(f"This chunk contains {len(paths)} modules related to {category}.\n\n")
            
            for path in sorted(paths):
                info = graph.modules[path]
                f.write(f"## {info.name}.py\n")
                f.write(f"- **Path**: `{path}`\n")
                f.write(f"- **Lines**: {info.lines}\n")
                
                if info.classes:
                    f.write(f"- **Classes**: {', '.join(info.classes)}\n")
                if info.functions:
                    f.write(f"- **Functions**: {', '.join(info.functions[:10])}")
                    if len(info.functions) > 10:
                        f.write(f" (+{len(info.functions) - 10} more)")
                    f.write("\n")
                    
                if info.docstring:
                    f.write(f"- **Purpose**: {info.docstring}\n")
                    
                # Dependencies within same project
                deps = []
                source = f"{info.package}.{info.name}" if info.package else info.name
                for src, dst in graph.edges:
                    if src == source and dst.startswith("office_converter"):
                        deps.append(dst)
                if deps:
                    f.write(f"- **Depends on**: {', '.join(deps[:5])}\n")
                    
                f.write("\n")
                
    print(f"   Generated context chunks in {chunks_dir}")


def generate_markdown_report(graph: DependencyGraph, output_path: str):
    """Generate human-readable architecture documentation."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# 🗺️ Project Architecture Map\n\n")
        f.write(f"**Generated**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Project**: {graph.project_root}\n\n")
        
        # Summary
        f.write("## 📊 Summary\n\n")
        f.write(f"| Metric | Count |\n")
        f.write(f"|:---|---:|\n")
        f.write(f"| Total Modules | {len(graph.modules)} |\n")
        f.write(f"| Total Dependencies | {len(graph.edges)} |\n")
        f.write(f"| Total Lines | {sum(m.lines for m in graph.modules.values())} |\n\n")
        
        # By category
        f.write("## 🏗️ Architecture Layers\n\n")
        
        category_icons = {
            "view": "🖥️",
            "model": "📦",
            "controller": "⚙️",
            "util": "🔧",
            "test": "🧪",
            "script": "📜",
            "other": "📄"
        }
        
        for category, paths in sorted(graph.clusters.items()):
            icon = category_icons.get(category, "📄")
            f.write(f"### {icon} {category.title()} ({len(paths)} modules)\n\n")
            
            for path in sorted(paths)[:10]:  # Limit display
                info = graph.modules[path]
                classes_str = f" - Classes: {', '.join(info.classes[:3])}" if info.classes else ""
                f.write(f"- `{path}` ({info.lines} lines){classes_str}\n")
                
            if len(paths) > 10:
                f.write(f"- ... and {len(paths) - 10} more\n")
            f.write("\n")
            
        # Dependency diagram (Mermaid)
        f.write("## 🔗 Dependency Diagram\n\n")
        f.write("```mermaid\ngraph LR\n")
        
        # Simplified diagram - show category-level dependencies
        category_deps = defaultdict(set)
        for src, dst in graph.edges:
            src_cat = None
            dst_cat = None
            for path, info in graph.modules.items():
                full_name = f"{info.package}.{info.name}" if info.package else info.name
                if full_name == src or info.name == src:
                    src_cat = info.category
                if dst.startswith("office_converter"):
                    # Find matching module
                    for p2, i2 in graph.modules.items():
                        if dst.endswith(i2.name) or dst == f"{i2.package}.{i2.name}":
                            dst_cat = i2.category
                            break
            if src_cat and dst_cat and src_cat != dst_cat:
                category_deps[src_cat].add(dst_cat)
                
        for src_cat, deps in category_deps.items():
            for dst_cat in deps:
                f.write(f"    {src_cat} --> {dst_cat}\n")
        f.write("```\n\n")
        
        f.write("---\n*Generated by context_mapper.py*\n")
        
    print(f"   Generated report: {output_path}")


def generate_json_output(graph: DependencyGraph, output_path: str):
    """Generate machine-readable JSON output."""
    data = {
        "project_root": graph.project_root,
        "modules": {k: asdict(v) for k, v in graph.modules.items()},
        "edges": graph.edges,
        "clusters": graph.clusters
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"   Generated JSON: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate project architecture map")
    parser.add_argument("project_path", nargs="?", default=".", help="Path to project root")
    parser.add_argument("--output", choices=["json", "md", "both", "all"], default="all",
                        help="Output format (all includes context chunks)")
    parser.add_argument("--output-dir", default=".context", help="Output directory")
    
    args = parser.parse_args()
    
    project_path = os.path.abspath(args.project_path)
    output_dir = os.path.join(project_path, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 60)
    print("🗺️  PROJECT CONTEXT MAPPER")
    print("=" * 60)
    
    # Build graph
    graph = build_dependency_graph(project_path)
    
    # Generate outputs
    if args.output in ["json", "both", "all"]:
        generate_json_output(graph, os.path.join(output_dir, "dependency_graph.json"))
        
    if args.output in ["md", "both", "all"]:
        generate_markdown_report(graph, os.path.join(output_dir, "context_map.md"))
        
    if args.output == "all":
        generate_context_chunks(graph, output_dir)
        
    print("=" * 60)
    print(f"✅ Done! Output saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
