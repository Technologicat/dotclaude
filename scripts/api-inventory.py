#!/usr/bin/env python3
"""List the public API of a Python package, one line per public symbol.

Why this exists: grep finds a helper only if you can guess its *name*, and the
expensive failure mode is the one where you cannot — you go looking for
"fragmentize" and the function is called `search_string_to_fragments`. Reading a
page of names fixes that; searching cannot. So this prints the page: every
`__all__` entry in a package, with its signature and the first line of its
docstring, grouped by module.

Deploy by symlinking onto PATH, so this stays the single copy:

    ln -s ~/.claude/scripts/api-inventory ~/.local/bin/api-inventory

Two modes, because the fleet contains cases that defeat each one:

  static (default)  Parse the source with `ast`. Imports nothing, so it works on
                    a package whose dependencies are heavy (torch, DPG), whose
                    import has side effects, or which is not installed in the
                    active venv at all. Resolves `__all__` only when it is a
                    literal list/tuple/set of strings.

  --import          Import the package and introspect it. Handles a computed
                    `__all__` (`unpythonic.llist` does `__all__ = _exports`),
                    and anything else built at runtime. Costs the import.

Static mode is the default because it always works; the report names any module
whose `__all__` it could not resolve, so you know when to re-run with --import.

**Macro-using packages make --import actively dangerous, hence a guard.** A module
carrying an mcpyrate `from ... import macros, ...` cannot be imported under regular
Python — the name does not exist, so it raises ImportError. The damage is that CPython
writes the `.pyc` when it *compiles*, before the failing import body ever runs, so the
cache is left holding unexpanded bytecode with an mtime that says it is current. The
next `macropython` run then trusts that cache, skips expansion, and fails with the very
same ImportError — now under the tool that was supposed to fix it, which is what makes
it baffling rather than merely annoying. So
--import refuses when it finds such a module, and --macros enables the expander first
(`import mcpyrate.activate`) for the case where you do want to introspect one. To
repair a tree this already happened to: `macropython -C <dir>`.
"""

import argparse
import ast
import importlib
import inspect
import os
import pkgutil
import sys
import types

from typing import List, Optional, Tuple

SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "build", "dist", ".tox", ".eggs",
             "00_stuff", "00_old"}  # fleet scratch areas — a copy in there is not the package's API
TEST_DIRS = {"test", "tests"}

# One entry of the report: the symbol, how to call it, and what it is for.
# `maybe_signature` and `maybe_summary` are None when the source does not say
# (a re-exported name in static mode has neither).
Entry = Tuple[str, Optional[str], Optional[str]]


# --------------------------------------------------------------------------------
# static mode

def resolve_strings(node, bindings: dict, depth: int = 0) -> Optional[List[str]]:
    """Statically evaluate `node` to a list of strings, or None if that cannot be done.

    Handles the forms an `__all__` actually takes in the wild: a literal
    list/tuple/set, a name bound to one elsewhere in the module (`__all__ =
    _exports`), a concatenation of either, and a splat of one inside another.
    `bindings` maps each module-level name to the expression assigned to it.
    """
    if depth > 8:  # cheap guard against a cyclic binding
        return None
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        out = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.append(elt.value)
            elif isinstance(elt, ast.Starred):
                maybe_inner = resolve_strings(elt.value, bindings, depth + 1)
                if maybe_inner is None:
                    return None
                out.extend(maybe_inner)
            else:  # a non-literal element means we would under-report; say so instead
                return None
        return out
    if isinstance(node, ast.Name):
        maybe_bound = bindings.get(node.id)
        return resolve_strings(maybe_bound, bindings, depth + 1) if maybe_bound is not None else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        maybe_left = resolve_strings(node.left, bindings, depth + 1)
        maybe_right = resolve_strings(node.right, bindings, depth + 1)
        if maybe_left is None or maybe_right is None:
            return None
        return maybe_left + maybe_right
    return None


def mutations_of(tree: ast.Module, names: set, bindings: dict) -> Optional[List[str]]:
    """Collect module-level `X += [...]`, `X.extend([...])` and `X.append("...")` for X in `names`.

    Returns the accumulated additions, or None if any mutation is one a static
    read cannot follow. Mutations are gathered wherever they appear rather than
    in execution order, which is enough for an inventory: the set of exported
    names is the same either way, only their order can differ.
    """
    added = []
    for node in tree.body:
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add) \
                and isinstance(node.target, ast.Name) and node.target.id in names:
            maybe_more = resolve_strings(node.value, bindings)
            if maybe_more is None:
                return None
            added.extend(maybe_more)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name):
                continue
            if call.func.value.id not in names or len(call.args) != 1:
                continue
            if call.func.attr == "extend":
                maybe_more = resolve_strings(call.args[0], bindings)
                if maybe_more is None:
                    return None
                added.extend(maybe_more)
            elif call.func.attr == "append":
                arg = call.args[0]
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    return None
                added.append(arg.value)
    return added


def parse_all(tree: ast.Module) -> Tuple[Optional[List[str]], bool]:
    """Extract a module's `__all__`.

    Returns `(names, resolvable)`:

      - `(None, True)`   no `__all__` at all, i.e. no public API (the convention
                         `mcpyrate`'s troubleshooting doc states, and the fleet follows)
      - `(None, False)`  an `__all__` exists but is built in a way a static read cannot
                         follow — the caller should say so and suggest --import
      - `(names, True)`  resolved, in declaration order
    """
    bindings = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = node.value

    if "__all__" not in bindings:
        return None, True

    value = bindings["__all__"]
    maybe_names = resolve_strings(value, bindings)
    if maybe_names is None:
        return None, False

    # Mutations may be written against `__all__` itself or against the name it
    # aliases (`_exports.extend(...)` ahead of `__all__ = _exports`), so watch both.
    watched = {"__all__"}
    if isinstance(value, ast.Name):
        watched.add(value.id)
    maybe_added = mutations_of(tree, watched, bindings)
    if maybe_added is None:
        return None, False
    return maybe_names + maybe_added, True


def signature_of(node) -> Optional[str]:
    """Render a def/class node's parameter list, or None if it has none to render."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return f"({ast.unparse(node.args)})"
    if isinstance(node, ast.ClassDef):
        for sub in node.body:  # a class advertises itself through __init__
            if isinstance(sub, ast.FunctionDef) and sub.name == "__init__":
                args = ast.unparse(sub.args)
                args = args.split(", ", 1)[1] if ", " in args else ""  # drop `self`
                return f"({args})"
        return "()"
    return None


def toplevel_nodes(tree: ast.Module) -> dict:
    """Map each module-level binding to the node that created it."""
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = node
    return out


def summary_of(node) -> Optional[str]:
    """First line of a node's docstring, or a constant's value, or None."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        maybe_doc = ast.get_docstring(node)
        if maybe_doc:
            for line in maybe_doc.splitlines():
                if line.strip():
                    return line.strip()
        return None
    if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
        if isinstance(node.value, ast.Constant):
            return f"= {node.value.value!r}"
        rendered = ast.unparse(node.value)
        return f"= {rendered}" if len(rendered) <= 40 else None
    return None


def scan_file(path: str) -> Tuple[Optional[List[Entry]], bool]:
    """Read one source file. Returns `(entries, resolvable)`; entries is None if no public API."""
    with open(path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=path)
        except SyntaxError as exc:
            print(f"api-inventory: cannot parse {path}: {exc}", file=sys.stderr)
            return None, True

    names, resolvable = parse_all(tree)
    if names is None:
        return None, resolvable

    nodes = toplevel_nodes(tree)
    entries = []
    for name in names:  # __all__ order mirrors the file, so keep it
        maybe_node = nodes.get(name)
        if maybe_node is None:  # re-exported from elsewhere; nothing local to describe
            entries.append((name, None, None))
        else:
            entries.append((name, signature_of(maybe_node), summary_of(maybe_node)))
    return entries, True


def module_name_for(path: str) -> str:
    """Derive a dotted module name by walking up while `__init__.py` keeps existing."""
    parts = [os.path.splitext(os.path.basename(path))[0]]
    directory = os.path.dirname(os.path.abspath(path))
    while os.path.exists(os.path.join(directory, "__init__.py")):
        parts.append(os.path.basename(directory))
        directory = os.path.dirname(directory)
    if parts[0] == "__init__":
        parts.pop(0)
    return ".".join(reversed(parts))


def walk_sources(root: str, include_tests: bool):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        skip = SKIP_DIRS if include_tests else SKIP_DIRS | TEST_DIRS
        dirnames[:] = sorted(d for d in dirnames if d not in skip)
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                yield os.path.join(dirpath, filename)


# --------------------------------------------------------------------------------
# dynamic mode

def import_package(target: str):
    """Import `target`, given either a dotted name or a path to a package directory."""
    if os.path.exists(target):
        path = os.path.abspath(target)
        directory = path if os.path.isdir(path) else os.path.dirname(path)
        name = module_name_for(os.path.join(directory, "__init__.py"))
        # The package root's *parent* is what has to be on sys.path.
        for _ in range(name.count(".") + 1):
            directory = os.path.dirname(directory)
        sys.path.insert(0, directory)
        target = name
    return importlib.import_module(target)


def uses_macros(tree: ast.Module) -> bool:
    """Whether a module needs the mcpyrate expander to import at all.

    Two markers, both of the form `from module import <marker>, name, ...`:
    `macros` binds macros for this module, and `dialects` enables the whole-module
    transformer. Each is a *marker* the expander consumes rather than a real name, so
    under regular Python both raise `ImportError: cannot import name ...`.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(alias.name in ("macros", "dialects") for alias in node.names):
                return True
    return False


def find_macro_modules(target: str, include_tests: bool) -> List[str]:
    """Source files under `target` that import macros. Parses only; imports nothing."""
    found = []
    if not os.path.exists(target):
        return found
    for path in walk_sources(target, include_tests):
        with open(path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=path)
            except SyntaxError:
                continue
        if uses_macros(tree):
            found.append(path)
    return found


def is_test_module(name: str) -> bool:
    """Whether a dotted module name has a test package anywhere in its path."""
    return any(part in TEST_DIRS for part in name.split("."))


def submodules_of(package, include_tests: bool) -> List[str]:
    """Every importable submodule name under `package`, imported so it is introspectable.

    An empty `__init__.py` (`raven.common` has one) means nothing lands in
    `sys.modules` on import of the package alone, so walk and import first.
    """
    prefix = package.__name__ + "."
    if hasattr(package, "__path__"):
        for info in pkgutil.walk_packages(package.__path__, prefix):
            if not include_tests and is_test_module(info.name):
                continue
            try:
                importlib.import_module(info.name)
            except Exception as exc:  # a broken optional dep should not sink the report
                print(f"api-inventory: skipping {info.name}: {exc}", file=sys.stderr)
    # Enumerate from sys.modules rather than by testing `dir(package)` entries for
    # module-ness: an object imported from a submodule can share the submodule's name
    # and shadow it in the parent namespace, which would drop it from the list.
    # (mcpyrate's doc/troubleshooting.md, "How to list the whole public API".)
    # Filter on the way out too: an unrelated import may already have pulled a test
    # module into sys.modules, where the walk above would never have seen it.
    return sorted(name for name in sys.modules
                  if (name == package.__name__ or name.startswith(prefix))
                  and (include_tests or not is_test_module(name)))


def introspect(module) -> Optional[List[Entry]]:
    maybe_all = getattr(module, "__all__", None)
    if maybe_all is None:
        return None
    entries = []
    for name in maybe_all:
        obj = getattr(module, name, None)
        if obj is None:
            entries.append((name, None, "(declared in __all__ but not present)"))
            continue
        signature = None
        if callable(obj):
            try:
                signature = str(inspect.signature(obj))
            except (TypeError, ValueError):
                signature = "(...)"
        maybe_doc = inspect.getdoc(obj) if not isinstance(obj, types.ModuleType) else None
        summary = None
        if maybe_doc:
            for line in maybe_doc.splitlines():
                if line.strip():
                    summary = line.strip()
                    break
        if summary is None and not callable(obj):
            rendered = repr(obj)
            summary = f"= {rendered}" if len(rendered) <= 40 else None
        entries.append((name, signature, summary))
    return entries


# --------------------------------------------------------------------------------
# report

def emit(title: str, entries: List[Entry], width: int, names_only: bool) -> None:
    print(f"\n{title}")
    for name, maybe_signature, maybe_summary in entries:
        call = f"{name}{maybe_signature}" if maybe_signature else name
        if names_only or not maybe_summary:
            print(f"  {call}")
            continue
        summary = maybe_summary
        if len(summary) > width:
            summary = summary[:width - 1].rstrip() + "…"  # horizontal ellipsis
        print(f"  {call} — {summary}")  # em dash


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List the public API (every __all__ entry) of a Python package.")
    parser.add_argument("targets", nargs="+", metavar="TARGET",
                        help="package directory, source file, or (with --import) dotted module name")
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="import and introspect instead of parsing source; "
                             "needed for a computed __all__")
    parser.add_argument("--macros", action="store_true",
                        help="with --import: enable mcpyrate before importing, so macro-using "
                             "modules can be imported at all (and without corrupting their bytecode cache)")
    parser.add_argument("--names-only", action="store_true",
                        help="omit docstring summaries")
    parser.add_argument("--include-tests", action="store_true",
                        help="do not skip test/ and tests/ directories")
    parser.add_argument("--width", type=int, default=100, metavar="N",
                        help="truncate summaries to N characters (default: 100)")
    args = parser.parse_args()

    unresolved, private = [], 0

    if args.do_import and args.macros:
        # Must precede any import of the target: the expander works through an import hook,
        # so a module already imported without it stays unexpanded (and has a bad .pyc).
        try:
            import mcpyrate.activate  # noqa: F401 -- imported for its import-hook side effect
        except ImportError:
            print("api-inventory: --macros needs mcpyrate, which is not importable here. "
                  "Run from a venv that has it.", file=sys.stderr)
            return 1

    for target in args.targets:
        if args.do_import:
            # Importing a macro-using module under regular Python fails with
            # "cannot import name 'macros'" *and* writes an unexpanded .pyc whose mtime
            # says it is current — so the next macropython run silently uses the bad
            # bytecode. Refuse rather than cause that; static mode never has the problem.
            if not args.macros:
                macro_modules = find_macro_modules(target, args.include_tests)
                if macro_modules:
                    listed = "\n  ".join(macro_modules[:5])
                    more = f"\n  ... and {len(macro_modules) - 5} more" if len(macro_modules) > 5 else ""
                    print(f"api-inventory: {target} contains macro-using modules:\n  {listed}{more}\n"
                          f"Importing those under regular Python corrupts their bytecode cache. "
                          f"Re-run with --macros, or drop --import to read the source instead. "
                          f"If a run already happened, clear the caches with `macropython -C {target}`.",
                          file=sys.stderr)
                    return 1
            try:
                package = import_package(target)
            except Exception as exc:
                print(f"api-inventory: cannot import {target}: {exc}", file=sys.stderr)
                return 1
            for name in submodules_of(package, args.include_tests):
                maybe_entries = introspect(sys.modules[name])
                if maybe_entries is None:
                    private += 1
                elif maybe_entries:
                    emit(f"{name}:", maybe_entries, args.width, args.names_only)
        else:
            if not os.path.exists(target):
                print(f"api-inventory: no such path: {target} "
                      f"(a dotted module name needs --import)", file=sys.stderr)
                return 1
            for path in walk_sources(target, args.include_tests):
                maybe_entries, resolvable = scan_file(path)
                if not resolvable:
                    unresolved.append(path)
                elif maybe_entries is None:
                    private += 1
                elif maybe_entries:
                    emit(f"{module_name_for(path)}:  [{path}]", maybe_entries,
                         args.width, args.names_only)

    notes = []
    if private:
        notes.append(f"{private} module(s) declare no __all__ (no public API)")
    if unresolved:
        listed = ", ".join(unresolved)
        notes.append(f"__all__ is computed, so a static read cannot see it, in: {listed}\n"
                     f"  Re-run with --import to include these.")
    if notes:
        print("\n" + "\n".join(f"note: {n}" for n in notes), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
