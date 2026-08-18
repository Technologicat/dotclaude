#!/usr/bin/env python3
"""Did moving a Python function change it?

Compares each named function between a git revision and the working tree, at the level of its parsed
body rather than its text, so that a pure relocation reads as "unchanged" however far it moved or
re-indented. Reports the difference when there is one.

The problem it solves is that a move produces a diff nobody can review: a block of deletions and a block
of near-identical insertions, where the only thing worth knowing — *is the code the same?* — is exactly
what reading it cannot establish. A human checking hundreds of lines for the absence of change is a human
about to miss one. This answers that question directly, so the check can stand in for the review.

Differences it deliberately ignores, because a move causes them and they carry no meaning:

  - indentation, at every level;
  - line wrapping inside docstrings, which shifts when a function dedents;
  - a leading `self` parameter, when `--to-method` says a function became a method;
  - `self.` in front of the names given to `--renamed-to-self`, for call sites that had to follow.

Everything else counts as a change, including a reordered argument, an altered default, and any edit to
the code itself.

Usage:

    check-move.py FILE FUNC [FUNC ...]                     # compare against HEAD
    check-move.py --rev HEAD~3 FILE FUNC [FUNC ...]        # ...or any revision
    check-move.py --to-method FILE FUNC [FUNC ...]         # each function gained `self`
    check-move.py --to-method --renamed-to-self foo,bar FILE FUNC [FUNC ...]

`--renamed-to-self` is for the batch case: when several sibling functions become methods together, calls
between them change from `foo()` to `self.foo()`, and those names must be normalized or every body that
calls a sibling reads as modified. Pass the whole batch.

Exit status is 0 when every function checks out, 1 otherwise, so it can gate a commit.
"""

import argparse
import ast
import difflib
import subprocess
import sys


def _function(source: str, name: str) -> ast.FunctionDef:
    """The definition of `name` in `source`, wherever it is nested. Raises `LookupError` if absent."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise LookupError(name)


def _normalizer(self_names: set[str]) -> ast.NodeTransformer:
    """A transformer that erases the differences a move is allowed to cause."""
    class Normalize(ast.NodeTransformer):
        def visit_Attribute(self, node):
            self.generic_visit(node)
            if (isinstance(node.value, ast.Name) and node.value.id == "self"
                    and node.attr in self_names):
                return ast.Name(id=node.attr, ctx=node.ctx)
            return node

        def visit_Constant(self, node):
            # Docstrings and other multi-line strings re-wrap when the code around them dedents.
            if isinstance(node.value, str) and "\n" in node.value:
                return ast.Constant(value=" ".join(node.value.split()))
            return node

    return Normalize()


def _body(function: ast.FunctionDef, self_names: set[str]) -> str:
    module = ast.Module(body=function.body, type_ignores=[])
    return ast.unparse(_normalizer(self_names).visit(module))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that moving a function did not change it.")
    parser.add_argument("file", help="path to the file, as git knows it")
    parser.add_argument("functions", nargs="+", help="the functions that moved")
    parser.add_argument("--rev", default="HEAD", help="revision to compare against (default: HEAD)")
    parser.add_argument("--to-method", action="store_true",
                        help="each function became a method, so expect a leading `self` parameter")
    parser.add_argument("--renamed-to-self", default="",
                        help="comma-separated names whose call sites gained a `self.` prefix; "
                             "defaults to the functions being checked")
    args = parser.parse_args()

    before = subprocess.run(["git", "show", f"{args.rev}:{args.file}"],
                            capture_output=True, text=True)
    if before.returncode:
        print(f"cannot read {args.file} at {args.rev}: {before.stderr.strip()}", file=sys.stderr)
        return 2
    after = open(args.file, encoding="utf-8").read()

    self_names = set(filter(None, args.renamed_to_self.split(","))) or set(args.functions)

    every_one_held = True
    for name in args.functions:
        try:
            old, new = _function(before.stdout, name), _function(after, name)
        except LookupError as exc:
            print(f"  {name:28s} NOT FOUND ({'before' if exc.args[0] else 'after'})")
            every_one_held = False
            continue

        old_body, new_body = _body(old, self_names), _body(new, self_names)
        old_args = [a.arg for a in old.args.args]
        new_args = [a.arg for a in new.args.args]
        expected_args = (["self"] + old_args) if args.to_method else old_args

        held = old_body == new_body and new_args == expected_args
        every_one_held &= held
        print(f"  {name:28s} {'OK' if held else 'CHANGED'}")
        if new_args != expected_args:
            print(f"      arguments: {old_args} -> {new_args}, expected {expected_args}")
        if old_body != new_body:
            for line in difflib.unified_diff(old_body.splitlines(), new_body.splitlines(),
                                             lineterm="", n=1):
                print("     ", line)

    print("\nINVARIANT HELD" if every_one_held else "\nINVARIANT VIOLATED")
    return 0 if every_one_held else 1


if __name__ == "__main__":
    sys.exit(main())
