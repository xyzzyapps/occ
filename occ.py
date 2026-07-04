#!/usr/bin/env python3
"""Orthodox C++ Checker (occ)

This script parses C++ source files using libclang and checks them for compliance
with the Orthodox C++ design subset. It flags violations of rules regarding exceptions,
RTTI, virtual/multiple inheritance, and forbidden heavy standard library headers.
"""

import os
import sys
import argparse
import clang.cindex

FORBIDDEN_HEADERS = {
    "iostream", "sstream", "fstream", "thread", "future", "regex"
}

class Violation:
    """Represents a single rule violation in a source file."""
    def __init__(self, filename, line, column, message):
        self.filename = filename
        self.line = line
        self.column = column
        self.message = message

    def __str__(self):
        return f"{self.filename}:{self.line}:{self.column}: violation: {self.message}"

def setup_libclang():
    """Locate and configure libclang.dll on Windows or standard paths on other platforms."""
    if os.name != "nt":
        # On non-Windows platforms, libclang is usually found in standard paths automatically
        return True

    # Windows specific search paths (prioritizing UCRT64)
    paths = [
        r"C:\msys64\ucrt64\bin\libclang.dll",
        r"C:\msys64\mingw64\bin\libclang.dll",
        r"C:\msys64\clang64\bin\libclang.dll",
        r"C:\Program Files\LLVM\bin\libclang.dll",
    ]
    
    # Also search PATH environment variable
    for path in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(path, "libclang.dll")
        if os.path.exists(candidate) and candidate not in paths:
            paths.append(candidate)
            
    for path in paths:
        if os.path.exists(path):
            try:
                dll_dir = os.path.dirname(path)
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(dll_dir)
                clang.cindex.Config.set_library_file(path)
                return True
            except Exception:
                pass
    return False

def get_source_line(filepath, line_num):
    """Retrieve a specific line of source code from a file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            if 0 < line_num <= len(lines):
                return lines[line_num - 1].strip()
    except Exception:
        pass
    return ""

def is_pure_interface(class_cursor):
    """Check if a class or struct declaration qualifies as a pure interface.
    
    Under Orthodox C++, a pure interface has no fields and all methods
    (excluding destructors) are pure virtual.
    """
    defn = class_cursor.get_definition()
    if not defn:
        return False
        
    for child in defn.get_children():
        if child.kind == clang.cindex.CursorKind.FIELD_DECL:
            return False
        if child.kind == clang.cindex.CursorKind.CXX_METHOD:
            # Trivial destructor check
            if child.spelling.startswith("~"):
                continue
            if not child.is_pure_virtual_method():
                return False
    return True

def check_node(node, filepath, violations, rules_options):
    """Inspect an AST node for Orthodox C++ rule violations."""
    # 1. Exception Check
    if node.kind == clang.cindex.CursorKind.CXX_TRY_STMT:
        violations.append(Violation(filepath, node.location.line, node.location.column, 
                                    "Exception handling (try block) is forbidden."))
    elif node.kind == clang.cindex.CursorKind.CXX_CATCH_STMT:
        violations.append(Violation(filepath, node.location.line, node.location.column, 
                                    "Exception handling (catch block) is forbidden."))
    elif node.kind == clang.cindex.CursorKind.CXX_THROW_EXPR:
        violations.append(Violation(filepath, node.location.line, node.location.column, 
                                    "Exception throwing is forbidden."))

    # 2. RTTI Check
    elif node.kind == clang.cindex.CursorKind.CXX_DYNAMIC_CAST_EXPR:
        violations.append(Violation(filepath, node.location.line, node.location.column, 
                                    "dynamic_cast is forbidden (RTTI is disabled)."))
    elif node.kind == clang.cindex.CursorKind.CXX_TYPEID_EXPR:
        violations.append(Violation(filepath, node.location.line, node.location.column, 
                                    "typeid is forbidden (RTTI is disabled)."))

    # 3. Inheritance Checks
    elif node.kind == clang.cindex.CursorKind.CXX_BASE_SPECIFIER:
        if node.is_virtual_base():
            violations.append(Violation(filepath, node.location.line, node.location.column, 
                                        f"Virtual inheritance from base class '{node.spelling}' is forbidden."))
            
    elif node.kind in (clang.cindex.CursorKind.CLASS_DECL, clang.cindex.CursorKind.STRUCT_DECL):
        # Count base classes
        bases = [child for child in node.get_children() if child.kind == clang.cindex.CursorKind.CXX_BASE_SPECIFIER]
        if len(bases) > 1:
            # Multiple inheritance is allowed only if all bases except the first are pure interfaces
            for extra_base in bases[1:]:
                # Find definition of the base class
                base_ref = extra_base.referenced
                if base_ref and not is_pure_interface(base_ref):
                    violations.append(Violation(filepath, extra_base.location.line, extra_base.location.column, 
                                                f"Multiple inheritance is forbidden unless base classes are pure interfaces. "
                                                f"Base class '{extra_base.spelling}' is not a pure interface."))

    # 4. Inclusion Checks (Forbidden Headers)
    elif node.kind == clang.cindex.CursorKind.INCLUSION_DIRECTIVE:
        header_name = ""
        inc_file = node.get_included_file()
        if inc_file:
            header_name = os.path.basename(inc_file.name)
        if not header_name:
            header_name = node.displayname or node.spelling
            
        header_name = header_name.strip('<>"')
        
        # Fallback: check source line if header name couldn't be extracted cleanly
        if not header_name:
            line_str = get_source_line(filepath, node.location.line)
            for fh in FORBIDDEN_HEADERS:
                if f"<{fh}>" in line_str or f'"{fh}"' in line_str:
                    header_name = fh
                    break

        if header_name in FORBIDDEN_HEADERS:
            violations.append(Violation(filepath, node.location.line, node.location.column, 
                                        f"Inclusion of forbidden header <{header_name}> (heavy standard library)."))

    # Advanced rule checks:

    # 5. Template Ban Check
    if rules_options.get("ban_templates"):
        # Check template declarations
        if node.kind in (clang.cindex.CursorKind.CLASS_TEMPLATE, 
                         clang.cindex.CursorKind.FUNCTION_TEMPLATE, 
                         clang.cindex.CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION):
            violations.append(Violation(filepath, node.location.line, node.location.column,
                                        f"Templates are forbidden: '{node.spelling}'."))
        # Check template type usage (e.g. instantiations in variables, fields, parameters)
        elif node.kind in (clang.cindex.CursorKind.VAR_DECL, clang.cindex.CursorKind.FIELD_DECL, clang.cindex.CursorKind.PARM_DECL) and node.type is not None and node.type.get_num_template_arguments() > 0:
            violations.append(Violation(filepath, node.location.line, node.location.column,
                                        f"Template instantiation/type '{node.type.spelling}' is forbidden."))

    # 6. Preprocessor Ban Check
    if rules_options.get("ban_preprocessor"):
        if node.kind == clang.cindex.CursorKind.MACRO_DEFINITION:
            violations.append(Violation(filepath, node.location.line, node.location.column,
                                        f"Macro definition is forbidden: '#define {node.spelling}'."))
        elif node.kind == clang.cindex.CursorKind.MACRO_INSTANTIATION:
            violations.append(Violation(filepath, node.location.line, node.location.column,
                                        f"Macro expansion is forbidden: '{node.spelling}'."))

    # 7. Heap Allocation Ban Check
    if rules_options.get("ban_heap"):
        if node.kind == clang.cindex.CursorKind.CXX_NEW_EXPR:
            violations.append(Violation(filepath, node.location.line, node.location.column,
                                        "C++ heap allocation ('new') is forbidden."))
        elif node.kind == clang.cindex.CursorKind.CXX_DELETE_EXPR:
            violations.append(Violation(filepath, node.location.line, node.location.column,
                                        "C++ heap deallocation ('delete') is forbidden."))
        elif node.kind == clang.cindex.CursorKind.CALL_EXPR:
            # Check C standard library allocators
            if node.spelling in ("malloc", "calloc", "realloc", "free"):
                violations.append(Violation(filepath, node.location.line, node.location.column,
                                            f"C standard library allocator call '{node.spelling}' is forbidden."))

    # 8. Operator Overloading Ban Check
    if rules_options.get("ban_operators"):
        if node.kind == clang.cindex.CursorKind.CXX_METHOD:
            if node.spelling.startswith("operator") and node.spelling != "operator=":
                violations.append(Violation(filepath, node.location.line, node.location.column,
                                            f"Custom operator overloading is forbidden: '{node.spelling}'."))

    # 9. Lambda Expressions Ban Check
    if rules_options.get("ban_lambdas"):
        if node.kind == clang.cindex.CursorKind.LAMBDA_EXPR:
            violations.append(Violation(filepath, node.location.line, node.location.column,
                                        "Lambda expressions are forbidden."))

    # 10. Enforce explicit on single-argument constructors
    if rules_options.get("enforce_explicit"):
        if node.kind == clang.cindex.CursorKind.CONSTRUCTOR:
            params = [c for c in node.get_children() if c.kind == clang.cindex.CursorKind.PARM_DECL]
            if len(params) == 1:
                class_name = ""
                if node.semantic_parent:
                    class_name = node.semantic_parent.spelling
                param_type = params[0].type.spelling
                
                is_copy_or_move = False
                if class_name:
                    if f"{class_name} &" in param_type or f"{class_name} &&" in param_type:
                        is_copy_or_move = True
                
                if not is_copy_or_move:
                    tokens = list(node.get_tokens())
                    is_explicit = any(t.spelling == "explicit" for t in tokens)
                    if not is_explicit:
                        violations.append(Violation(filepath, node.location.line, node.location.column,
                                                    f"Single-argument constructor '{node.spelling}' must be declared 'explicit'."))

def traverse_ast(node, filepath, violations, rules_options):
    """Recursively traverse the AST to check nodes in the target file."""
    # Ensure the node belongs to the file being checked
    if node.location.file and os.path.abspath(node.location.file.name) == os.path.abspath(filepath):
        check_node(node, filepath, violations, rules_options)
        
    for child in node.get_children():
        traverse_ast(child, filepath, violations, rules_options)

def get_ucrt64_includes():
    """Retrieve standard system include paths from the MSYS2 UCRT64 toolchain."""
    includes = []
    ucrt_base = r"C:\msys64\ucrt64"
    if os.path.exists(ucrt_base):
        # Base C header directory
        includes.append(f"-isystem{os.path.join(ucrt_base, 'include')}")
        
        # C++ header directory
        cpp_base = os.path.join(ucrt_base, "include", "c++")
        if os.path.exists(cpp_base):
            for entry in os.listdir(cpp_base):
                entry_path = os.path.join(cpp_base, entry)
                if os.path.isdir(entry_path):
                    includes.append(f"-isystem{entry_path}")
                    # Machine-specific target directories (e.g. x86_64-w64-mingw32)
                    target_specific = os.path.join(entry_path, "x86_64-w64-mingw32")
                    if os.path.exists(target_specific):
                        includes.append(f"-isystem{target_specific}")
    return includes

def check_file(filepath, rules_options, verbose=False):
    """Parse and check a single C++ source file."""
    print(f"Checking {filepath}...")
    index = clang.cindex.Index.create()
    
    # Parse options: detailed preprocessing is needed to capture inclusion directives
    parse_options = clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
    
    # Standard compiler arguments with UCRT64 system includes
    args = ["-std=c++17", "-x", "c++"] + get_ucrt64_includes()
    
    try:
        tu = index.parse(filepath, args=args, options=parse_options)
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return False, []

    violations = []
    
    # Log parsing diagnostics (compiler errors/warnings)
    has_compile_errors = False
    for diag in tu.diagnostics:
        diag_file = diag.location.file.name if diag.location.file else "unknown"
        is_target_file = diag_file != "unknown" and os.path.abspath(diag_file) == os.path.abspath(filepath)
        
        if diag.severity >= clang.cindex.Diagnostic.Error:
            if is_target_file:
                print(f"Parser/Compiler Error in {diag_file}:{diag.location.line}:{diag.location.column}: {diag.spelling}")
                has_compile_errors = True
            elif verbose:
                print(f"System/Header Error in {diag_file}:{diag.location.line}:{diag.location.column}: {diag.spelling}")
        elif verbose:
            print(f"Diagnostic in {diag_file}:{diag.location.line}:{diag.location.column}: {diag.spelling}")
            
    # Even if there are compiler errors, we can still attempt to run rule checks on the partial AST
    traverse_ast(tu.cursor, filepath, violations, rules_options)
    
    return not has_compile_errors, violations

def main():
    parser = argparse.ArgumentParser(description="Enforce Orthodox C++ constraints on source files.")
    parser.add_argument("path", help="Path to a C++ source file or directory of source files.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed compiler diagnostics.")
    parser.add_argument("--ban-templates", action="store_true", help="Ban all template declarations and usages.")
    parser.add_argument("--ban-preprocessor", action="store_true", help="Ban all macro definitions and expansions.")
    parser.add_argument("--ban-heap", action="store_true", help="Ban C++ new/delete and standard C library allocation functions.")
    parser.add_argument("--ban-operators", action="store_true", help="Ban custom operator overloading declarations (excluding operator=).")
    parser.add_argument("--ban-lambdas", action="store_true", help="Ban all C++ lambda expressions.")
    parser.add_argument("--enforce-explicit", action="store_true", help="Enforce that all single-argument constructors are marked 'explicit'.")
    args = parser.parse_args()

    if not setup_libclang():
        print("ERROR: Could not locate a working libclang.dll. Make sure LLVM is installed and libclang.dll is in your PATH.", file=sys.stderr)
        sys.exit(1)

    targets = []
    if os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                if file.endswith((".cpp", ".h", ".hpp", ".cc", ".cxx")):
                    targets.append(os.path.join(root, file))
    else:
        targets.append(args.path)

    rules_options = {
        "ban_templates": args.ban_templates,
        "ban_preprocessor": args.ban_preprocessor,
        "ban_heap": args.ban_heap,
        "ban_operators": args.ban_operators,
        "ban_lambdas": args.ban_lambdas,
        "enforce_explicit": args.enforce_explicit,
    }

    all_success = True
    total_violations = 0

    for target in targets:
        success, violations = check_file(target, rules_options, args.verbose)
        if not success:
            all_success = False
            
        if violations:
            all_success = False
            total_violations += len(violations)
            for violation in violations:
                print(violation)
        else:
            print(f"{target} passed.")

    if not all_success or total_violations > 0:
        print(f"\nFailed: Found {total_violations} violations/errors across files.")
        sys.exit(1)
    else:
        print("\nAll files conform to the Orthodox C++ subset.")
        sys.exit(0)

if __name__ == "__main__":
    main()
