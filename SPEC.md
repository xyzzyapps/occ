# Software Requirements Specification

**Product:** Orthodox C++ Checker (`occ`)  
**Version:** 1.0  
**Audience:** implementing agents and human maintainers  
**License:** MIT (see `LICENSE`)  
**Primary artifact:** `occ.py`

This document is the source of truth for what `occ` must do. Implement against these requirements, not against informal comments or deleted planning notes.

---

## 1. Purpose

`occ` is a command-line static analyzer. It parses C++ translation units with libclang and reports violations of the **Orthodox C++** subset: a deliberately small C++ dialect that avoids high-overhead language and library features.

The tool must be usable as:

- a local check on a single file
- a recursive check on a directory of C++ sources
- a CI step via process exit codes

## 2. Scope

### In scope

- Parse C++ files (and C++-like headers) with libclang.
- Walk the AST of the target file only (do not flag nodes whose location is another file).
- Enforce the always-on Orthodox rules in section 5.1.
- Enforce optional advanced rules when the matching CLI flags are set (section 5.2).
- Print human-readable violation lines and a non-zero exit status when any file fails.

### Out of scope

- Fixing source automatically.
- Full compilation or linking of a project.
- Language-server / IDE plugin protocol.
- CMake or other build-system integration (not required for v1).
- Enforcing `noexcept` (not required for v1).

## 3. Definitions

| Term | Meaning |
| --- | --- |
| Target file | The `.cpp` / `.cc` / `.cxx` / `.h` / `.hpp` path being checked |
| Violation | A rule failure with file, line, column, and message |
| Pure interface | A class/struct with no fields; every method except destructors is pure virtual |
| Orthodox C++ | The subset defined by the rules in this spec |

## 4. External interfaces

### 4.1 Command line

```
python occ.py [options] <file-or-directory-path>
```

| Option | Effect |
| --- | --- |
| `-v`, `--verbose` | Print parser diagnostics, including those outside the target file |
| `--ban-templates` | Enable template ban |
| `--ban-preprocessor` | Enable macro definition/expansion ban |
| `--ban-heap` | Enable heap-allocation ban |
| `--ban-operators` | Enable operator-overload ban |
| `--ban-lambdas` | Enable lambda ban |
| `--enforce-explicit` | Require `explicit` on single-argument constructors |

If `path` is a directory, walk it recursively and check every file whose name ends with `.cpp`, `.h`, `.hpp`, `.cc`, or `.cxx`.

### 4.2 Output

Each violation MUST be printed as:

```
<filepath>:<line>:<column>: violation: <message>
```

Additional status lines (which file is being checked, pass/fail summary) are allowed.

### 4.3 Exit codes

| Code | When |
| --- | --- |
| `0` | Every target parsed without target-file compiler errors **and** no rule violations |
| `1` | Any target-file parse/compiler error, any violation, missing libclang, or unreadable path handling that prevents a clean run |

A parse error in a **system/header** file MUST NOT fail the run unless `--verbose` is only for printing; target-file errors MUST fail the run.

### 4.4 Dependencies

- Python 3.12+
- `clang` Python bindings (`requirements.txt`)
- A working libclang shared library
  - Windows: search `C:\msys64\ucrt64\bin\libclang.dll`, `mingw64`, `clang64`, `C:\Program Files\LLVM\bin\libclang.dll`, then `PATH`
  - Non-Windows: rely on default libclang discovery

If libclang cannot be configured, print an error to stderr and exit `1`.

Parse arguments MUST include `-std=c++17 -x c++` plus, on Windows when MSYS2 UCRT64 exists, `-isystem` paths under `C:\msys64\ucrt64\include` (C and C++ headers, including `x86_64-w64-mingw32` target dirs).

Parse options MUST include `PARSE_DETAILED_PROCESSING_RECORD` so include directives and macros are visible.

## 5. Functional requirements

### 5.1 Always-on rules

**FR-EXC.** Forbid exception handling in the target file:

- `try` statements
- `catch` clauses
- `throw` expressions

**FR-RTTI.** Forbid RTTI in the target file:

- `dynamic_cast`
- `typeid`

**FR-INH-VIRT.** Forbid virtual inheritance.

**FR-INH-MULTI.** If a class/struct has more than one base, every base after the first MUST be a pure interface. Otherwise report a violation on the offending extra base.

**FR-HDR.** Forbid inclusion of these headers (by basename, with or without `<>` / quotes):

`iostream`, `sstream`, `fstream`, `thread`, `future`, `regex`

If the include filename cannot be resolved from the AST, fall back to scanning the source line for `<name>` or `"name"`.

### 5.2 Optional advanced rules

Apply only when the corresponding flag is set.

**FR-TPL** (`--ban-templates`). Forbid:

- class templates, function templates, and class template partial specializations
- variable, field, or parameter types that have template arguments (e.g. `std::vector<float>`)

**FR-PP** (`--ban-preprocessor`). Forbid macro definitions and macro instantiations. `#include` remains allowed.

**FR-HEAP** (`--ban-heap`). Forbid:

- `new` / `delete` expressions
- calls named `malloc`, `calloc`, `realloc`, or `free`

**FR-OP** (`--ban-operators`). Forbid method declarations whose spelling starts with `operator` except `operator=`.

**FR-LAM** (`--ban-lambdas`). Forbid lambda expressions.

**FR-EXPL** (`--enforce-explicit`). For constructors with exactly one parameter that is not a copy or move constructor (parameter type contains `ClassName &` or `ClassName &&`), require the `explicit` token among the constructor’s tokens.

### 5.3 Traversal

**FR-LOC.** Only check AST nodes whose `location.file` is the target file (absolute path compare). Recurse into all children so included files can still contribute children that belong to the target.

**FR-PARTIAL.** If the parser reports target-file errors, still run rule checks on the partial AST, then fail the file.

## 6. Non-functional requirements

**NFR-DET.** Same inputs and flags MUST produce the same violations (order may follow AST walk order).

**NFR-WIN.** Primary supported host is Windows with MSYS2 UCRT64 clang-libs; other hosts are best-effort via default libclang.

**NFR-DEP.** Runtime Python dependency list is only `clang` unless this spec is updated.

## 7. Examples

The `examples/` tree is the behavioral fixture set:

| File | Expected |
| --- | --- |
| `examples/valid.cpp` | No always-on violations |
| `examples/invalid_exceptions.cpp` | Exception-rule violations |
| `examples/invalid_rtti.cpp` | RTTI-rule violations |
| `examples/invalid_inheritance.cpp` | Inheritance-rule violations |
| `examples/invalid_advanced.cpp` | Violations when advanced flags are enabled |

## 8. Acceptance

A change is acceptable when:

1. Always-on rules still fire on the invalid examples and not on `valid.cpp`.
2. Each advanced flag independently enables its FR in section 5.2.
3. Exit code is `0` only for a fully clean run.
4. Violation lines match the format in 4.2.
5. Missing libclang is a hard failure, not a silent pass.

## 9. Implementation notes for agents

- Do not reintroduce planning files (`.todo/`, `TODO.md`) into version control.
- Prefer extending `check_node` + CLI flags over new entry points.
- Keep messages specific (what construct, which name when available).
- Do not treat system-header diagnostics as target failures.
- Update this SPEC when you add a rule, flag, header, or exit-code meaning.
