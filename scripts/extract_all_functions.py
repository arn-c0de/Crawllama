"""
Script to extract all functions and classes from the CrawlLama project.
Generates a complete overview of all functions, methods, and classes.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict


class FunctionExtractor(ast.NodeVisitor):
    """Extract functions and classes from Python AST."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.functions = []
        self.classes = []
        self.current_class = None
        
    def visit_FunctionDef(self, node):
        """Visit function definition."""
        # Get function signature
        args = [arg.arg for arg in node.args.args]
        
        # Get return annotation if exists
        return_type = ""
        if node.returns:
            return_type = f" -> {ast.unparse(node.returns)}"
        
        # Get docstring
        docstring = ast.get_docstring(node) or ""
        first_line = docstring.split('\n')[0] if docstring else ""
        
        func_info = {
            'name': node.name,
            'args': args,
            'return_type': return_type,
            'docstring': first_line,
            'lineno': node.lineno,
            'is_async': False,
            'class': self.current_class
        }
        
        self.functions.append(func_info)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        """Visit async function definition."""
        args = [arg.arg for arg in node.args.args]
        return_type = ""
        if node.returns:
            return_type = f" -> {ast.unparse(node.returns)}"
        
        docstring = ast.get_docstring(node) or ""
        first_line = docstring.split('\n')[0] if docstring else ""
        
        func_info = {
            'name': node.name,
            'args': args,
            'return_type': return_type,
            'docstring': first_line,
            'lineno': node.lineno,
            'is_async': True,
            'class': self.current_class
        }
        
        self.functions.append(func_info)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        """Visit class definition."""
        docstring = ast.get_docstring(node) or ""
        first_line = docstring.split('\n')[0] if docstring else ""
        
        # Get base classes
        bases = [ast.unparse(base) for base in node.bases]
        
        class_info = {
            'name': node.name,
            'bases': bases,
            'docstring': first_line,
            'lineno': node.lineno
        }
        
        self.classes.append(class_info)
        
        # Visit methods
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class


def extract_from_file(filepath: Path) -> Tuple[List[Dict], List[Dict]]:
    """Extract functions and classes from a Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(filepath))
        extractor = FunctionExtractor(str(filepath))
        extractor.visit(tree)
        
        return extractor.functions, extractor.classes
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return [], []


def scan_project(root_dir: Path) -> Dict[str, Tuple[List[Dict], List[Dict]]]:
    """Scan entire project for Python files."""
    results = {}
    
    # Directories to scan
    dirs_to_scan = ['core', 'tools', 'utils', 'tests', 'plugins', 'core/health', 'core/osint']
    
    # Also scan root level Python files
    for py_file in root_dir.glob('*.py'):
        if py_file.name.startswith('_'):
            continue
        rel_path = py_file.relative_to(root_dir)
        results[str(rel_path)] = extract_from_file(py_file)
    
    # Scan directories
    for dir_name in dirs_to_scan:
        dir_path = root_dir / dir_name
        if not dir_path.exists():
            continue
        
        for py_file in dir_path.rglob('*.py'):
            if py_file.name.startswith('_') and py_file.name != '__init__.py':
                continue
            
            rel_path = py_file.relative_to(root_dir)
            results[str(rel_path)] = extract_from_file(py_file)
    
    return results


def generate_report(results: Dict[str, Tuple[List[Dict], List[Dict]]], output_file: Path):
    """Generate comprehensive function overview."""
    
    with open(output_file, 'w', encoding='utf-8') as out_file:
        out_file.write("=== CRAWLLAMA PROJECT - ALL FUNCTIONS & CLASSES ===\n")
        out_file.write("Generated on: 2025-10-24\n")
        out_file.write("Complete analysis of all functions and classes\n\n")
        
        # Count statistics
        total_files = len(results)
        total_functions = sum(len(funcs) for funcs, _ in results.values())
        total_classes = sum(len(classes) for _, classes in results.values())
        
        out_file.write(f"STATISTICS:\n")
        out_file.write(f"- Files analyzed: {total_files}\n")
        out_file.write(f"- Total functions: {total_functions}\n")
        out_file.write(f"- Total classes: {total_classes}\n\n")
        out_file.write("="*80 + "\n\n")
        
        # Group by module
        modules = defaultdict(list)
        for filepath, (funcs, classes) in results.items():
            if '/' in filepath or '\\' in filepath:
                module = filepath.replace('\\', '/').split('/')[0]
            else:
                module = 'root'
            modules[module].append((filepath, funcs, classes))
        
        # Output by module
        for module in sorted(modules.keys()):
            out_file.write(f"\n## MODULE: {module.upper()}\n")
            out_file.write("="*80 + "\n\n")
            
            for filepath, funcs, classes in sorted(modules[module]):
                if not funcs and not classes:
                    continue
                
                out_file.write(f"### {filepath}\n\n")
                
                # Classes
                if classes:
                    out_file.write("**Classes:**\n")
                    for cls in classes:
                        bases = f"({', '.join(cls['bases'])})" if cls['bases'] else ""
                        out_file.write(f"  - class {cls['name']}{bases}\n")
                        if cls['docstring']:
                            out_file.write(f"    → {cls['docstring']}\n")
                    out_file.write("\n")
                
                # Functions
                if funcs:
                    out_file.write("**Functions:**\n")
                    
                    # Group by class
                    standalone = [func for func in funcs if func['class'] is None]
                    by_class = defaultdict(list)
                    for func in funcs:
                        if func['class']:
                            by_class[func['class']].append(func)
                    
                    # Standalone functions
                    for func in standalone:
                        prefix = "async " if func['is_async'] else ""
                        args_str = ", ".join(func['args'])
                        out_file.write(f"  - {prefix}def {func['name']}({args_str}){func['return_type']}\n")
                        if func['docstring']:
                            out_file.write(f"    → {func['docstring']}\n")
                    
                    # Class methods
                    for class_name in sorted(by_class.keys()):
                        out_file.write(f"\n  **Class {class_name}:**\n")
                        for func in by_class[class_name]:
                            prefix = "async " if func['is_async'] else ""
                            args_str = ", ".join(func['args'])
                            out_file.write(f"    - {prefix}{func['name']}({args_str}){func['return_type']}\n")
                            if func['docstring']:
                                out_file.write(f"      → {func['docstring']}\n")
                
                out_file.write("\n" + "-"*80 + "\n\n")
        
        out_file.write("\n" + "="*80 + "\n")
        out_file.write("END OF ANALYSIS\n")
        out_file.write("="*80 + "\n")


def main():
    """Main entry point."""
    # Go up one level from scripts/ to project root
    project_root = Path(__file__).parent.parent
    output_file = Path(__file__).parent / "all_functions_complete.txt"
    
    print("🔍 Scanning CrawlLama project...")
    results = scan_project(project_root)

    print(f"📝 Generating report...")
    generate_report(results, output_file)

    print(f"✅ Report created: {output_file}")
    print(f"\nStatistics:")
    total_files = len(results)
    total_functions = sum(len(funcs) for funcs, _ in results.values())
    total_classes = sum(len(classes) for _, classes in results.values())
    print(f"  Files: {total_files}")
    print(f"  Functions: {total_functions}")
    print(f"  Classes: {total_classes}")


if __name__ == "__main__":
    main()
