"""Tests for the `api-inventory` script.

The script's name has a hyphen, so it is loaded by path rather than by `import`.

What is worth pinning here is the *static* `__all__` resolver: it has to follow the
forms that occur in the fleet without ever silently under-reporting, since a name
missing from the inventory is exactly the failure the tool exists to prevent.
"""

import ast
import importlib.util
import pathlib
import subprocess
import sys

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "api-inventory.py"


def _load():
    spec = importlib.util.spec_from_file_location("api_inventory", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


api = _load()


def scan(tmp_path, source, name="m.py"):
    """Write `source` to a file and run the static scanner over it."""
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return api.scan_file(str(path))


# --------------------------------------------------------------------------------
# resolving __all__

def test_literal_list_resolves(tmp_path):
    entries, resolvable = scan(tmp_path, '__all__ = ["a", "b"]\ndef a(): pass\ndef b(): pass\n')
    assert resolvable
    assert [e[0] for e in entries] == ["a", "b"]


@pytest.mark.parametrize("literal", ['("a", "b")', '{"a", "b"}'])
def test_tuple_and_set_literals_resolve(tmp_path, literal):
    """A set loses the file-order convention, but it is still readable — report it, don't refuse."""
    entries, resolvable = scan(tmp_path, f'__all__ = {literal}\ndef a(): pass\ndef b(): pass\n')
    assert resolvable
    assert {e[0] for e in entries} == {"a", "b"}


def test_name_alias_resolves(tmp_path):
    """`__all__ = _exports`, the shape `unpythonic.llist` carried as a fossil."""
    entries, resolvable = scan(tmp_path, '_exports = ["a"]\n__all__ = _exports\ndef a(): pass\n')
    assert resolvable
    assert [e[0] for e in entries] == ["a"]


def test_concatenation_resolves(tmp_path):
    entries, resolvable = scan(tmp_path, '_x = ["a"]\n__all__ = _x + ["b"]\ndef a(): pass\ndef b(): pass\n')
    assert resolvable
    assert [e[0] for e in entries] == ["a", "b"]


def test_splat_resolves(tmp_path):
    entries, resolvable = scan(tmp_path, '_x = ["a"]\n__all__ = [*_x, "b"]\ndef a(): pass\ndef b(): pass\n')
    assert resolvable
    assert [e[0] for e in entries] == ["a", "b"]


def test_module_level_mutations_are_folded_in(tmp_path):
    entries, resolvable = scan(tmp_path, (
        '__all__ = ["a"]\n'
        '__all__ += ["b"]\n'
        '__all__.extend(["c"])\n'
        '__all__.append("d")\n'
    ))
    assert resolvable
    assert [e[0] for e in entries] == ["a", "b", "c", "d"]


def test_mutation_on_the_aliased_name_is_seen(tmp_path):
    """The full `llist` shape: mutate the alias, *then* bind it to `__all__`."""
    entries, resolvable = scan(tmp_path, '_exports = ["a"]\n_exports.extend(["b"])\n__all__ = _exports\n')
    assert resolvable
    assert [e[0] for e in entries] == ["a", "b"]


def test_computed_all_is_reported_not_guessed(tmp_path):
    """The whole point: under-reporting silently would defeat the tool."""
    entries, resolvable = scan(tmp_path, '__all__ = [n for n in dir()]\n')
    assert not resolvable
    assert entries is None


def test_partly_literal_all_is_unresolvable(tmp_path):
    """A list with one non-literal element must not resolve to just the literal ones."""
    entries, resolvable = scan(tmp_path, '__all__ = ["a", some_name]\ndef a(): pass\n')
    assert not resolvable
    assert entries is None


def test_unresolvable_mutation_poisons_the_result(tmp_path):
    entries, resolvable = scan(tmp_path, '__all__ = ["a"]\n__all__.extend(compute())\ndef a(): pass\n')
    assert not resolvable
    assert entries is None


def test_no_all_means_no_public_api(tmp_path):
    entries, resolvable = scan(tmp_path, 'def a(): pass\n')
    assert resolvable          # nothing went wrong...
    assert entries is None     # ...there is simply no public API


# --------------------------------------------------------------------------------
# what each entry says

def test_signature_and_summary(tmp_path):
    entries, _ = scan(tmp_path, (
        '__all__ = ["f"]\n'
        'def f(x, *, key=None):\n'
        '    """Do the thing.\n\n    More detail here.\n    """\n'
    ))
    name, signature, summary = entries[0]
    assert name == "f"
    assert signature == "(x, *, key=None)"
    assert summary == "Do the thing."


def test_class_signature_comes_from_init_without_self(tmp_path):
    entries, _ = scan(tmp_path, (
        '__all__ = ["C"]\n'
        'class C:\n'
        '    """A thing."""\n'
        '    def __init__(self, a, b=1): pass\n'
    ))
    assert entries[0] == ("C", "(a, b=1)", "A thing.")


def test_constant_shows_its_value(tmp_path):
    entries, _ = scan(tmp_path, '__all__ = ["K"]\nK = "hello"\n')
    assert entries[0] == ("K", None, "= 'hello'")


def test_reexported_name_has_no_signature_or_summary(tmp_path):
    """Nothing local describes it, and inventing something would be worse than silence."""
    entries, _ = scan(tmp_path, 'from elsewhere import thing\n__all__ = ["thing"]\n')
    assert entries[0] == ("thing", None, None)


# --------------------------------------------------------------------------------
# what the walk skips

def test_walk_skips_scratch_and_test_directories(tmp_path):
    for relative in ("pkg/real.py", "pkg/00_stuff/scratch.py", "pkg/tests/test_x.py"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("__all__ = []\n", encoding="utf-8")

    found = {pathlib.Path(p).name for p in api.walk_sources(str(tmp_path), include_tests=False)}
    assert found == {"real.py"}

    with_tests = {pathlib.Path(p).name for p in api.walk_sources(str(tmp_path), include_tests=True)}
    assert with_tests == {"real.py", "test_x.py"}     # scratch stays excluded either way


# --------------------------------------------------------------------------------
# the macro guard

@pytest.mark.parametrize("marker", ["macros", "dialects"])
def test_macro_markers_are_detected(tmp_path, marker):
    """Importing these under regular Python raises *and* writes unexpanded bytecode."""
    tree = ast.parse(f"from somewhere import {marker}, thing\n")
    assert api.uses_macros(tree)


def test_ordinary_import_is_not_flagged(tmp_path):
    assert not api.uses_macros(ast.parse("from somewhere import thing\n"))


def test_marker_must_come_first_to_count(tmp_path):
    """The expander only reads the marker in first position, so neither do we.

    `from m import thing, macros` imports a name that happens to be spelled `macros`;
    it needs no expander and must not be treated as macro-using.
    """
    assert not api.uses_macros(ast.parse("from somewhere import thing, macros\n"))


def test_a_partial_inventory_does_not_report_success(tmp_path):
    """A module that cannot be imported has to change the exit code.

    Skipped modules leave stdout looking exactly like a complete run, so the status is
    the only channel that can carry "there is more than this".
    """
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (package / "m.py").write_text("import nonexistent_dependency\n__all__ = []\n", encoding="utf-8")

    result = subprocess.run([sys.executable, str(SCRIPT), "--import", str(package)],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert "incomplete" in result.stderr
    assert "pkg.m" in result.stderr


# --------------------------------------------------------------------------------
# the two modes have to agree

def _unpythonic_path():
    """Where `sys.executable` would import `unpythonic` from, or None if it cannot.

    Probed with the *same* interpreter that will run the script, because that is the
    condition that actually matters — a `macropython` on PATH belongs to some other
    environment and says nothing about this one.
    """
    probe = subprocess.run(
        [sys.executable, "-c", "import mcpyrate, unpythonic; print(unpythonic.__path__[0])"],
        capture_output=True, text=True)
    return probe.stdout.strip() if probe.returncode == 0 else None


def test_static_and_import_modes_agree():
    """The invariant the two modes exist to share: same package, same answer.

    `unpythonic` is the fixture because it exercises the hard cases — an aliased
    `__all__` (`llist`), and modules that only import under the macro expander.
    """
    package = _unpythonic_path()
    if package is None:
        pytest.skip("needs mcpyrate and unpythonic importable by this interpreter")

    def symbols(target, extra_args):
        out = subprocess.run([sys.executable, str(SCRIPT), "--names-only", *extra_args, target],
                             capture_output=True, text=True).stdout
        pairs, module = set(), None
        for line in out.splitlines():
            if line and not line.startswith(" "):
                module = line.split(":")[0]
            elif line.startswith("  ") and module:
                pairs.add((module, line.strip().split("(")[0].strip()))
        return pairs

    static = symbols(package, [])
    imported = symbols("unpythonic", ["--import"])
    assert static, "static mode found nothing — the fixture is wrong, not the tool"
    assert static == imported


def test_import_mode_leaves_the_target_alone(tmp_path):
    """Reading a package must not write into it.

    Bytecode compiled for an introspection run goes to our own cache directory. The
    failure this pins is not untidiness: a `.pyc` compiled without the expander makes
    every macro-using module in the package fail to import afterwards, so a tool that
    left one behind would break the very package it was asked to describe.
    """
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("__all__ = ['x']\nx = 1\n", encoding="utf-8")
    (package / "m.py").write_text("__all__ = ['y']\ny = 2\n", encoding="utf-8")

    result = subprocess.run([sys.executable, str(SCRIPT), "--names-only", "--import", str(package)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "y" in result.stdout, "the fixture did not get imported at all"
    # A fresh package has no bytecode yet, so anything appearing here was written by us.
    assert not list(package.rglob("__pycache__")), "wrote bytecode into the target package"
