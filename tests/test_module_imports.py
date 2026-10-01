"""Cross-module import checks for files that cannot be imported without HA.

Almost every module here imports Home Assistant, so no test can simply import it
and `compileall` only validates syntax. A dropped sibling-module import is
therefore invisible to the suite and only shows up as a failed integration setup
at runtime. These tests read the source and prove the helpers a module calls are
really bound.
"""
import ast
import builtins
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'custom_components' / 'lotto_645'
MODULES = sorted(COMPONENT.glob('*.py'))
BUILTINS = frozenset(dir(builtins)) | {'__file__', '__name__', '__doc__', '__package__'}


def _tree(module: str) -> ast.Module:
    return ast.parse((COMPONENT / f'{module}.py').read_text(encoding='utf-8'))


def _referenced_names(tree: ast.Module) -> set[str]:
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


def _sibling_imports(tree: ast.Module, module_of) -> dict[str, set[str]]:
    """Map each `from .module import ...` to the names it binds.

    A star import binds everything the target module defines, matching Python.
    """
    imports: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ImportFrom) and node.level == 1 and node.module):
            continue
        names = imports.setdefault(node.module, set())
        for alias in node.names:
            if alias.name == '*':
                names.update(module_of(node.module))
            else:
                names.add(alias.asname or alias.name)
    return imports


def _exported_names(module: str) -> set[str]:
    """Return the public module-level names a sibling module defines."""
    names: set[str] = set()
    for node in _tree(module).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _own_bindings(tree: ast.Module, exports_of) -> set[str]:
    """Every name the module binds itself, by import or in any scope."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.Import):
            bound.update(
                (alias.asname or alias.name).split('.')[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == '*':
                    # `from .const import *` binds every public name it defines.
                    bound.update(
                        exports_of(node.module)
                        if node.level == 1 and node.module
                        else ()
                    )
                else:
                    bound.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
            arguments = getattr(node, 'args', None)
            if arguments is not None:
                for group in (arguments.posonlyargs, arguments.args, arguments.kwonlyargs):
                    bound.update(argument.arg for argument in group)
                for extra in (arguments.vararg, arguments.kwarg):
                    if extra is not None:
                        bound.add(extra.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Global | ast.Nonlocal):
            bound.update(node.names)
    return bound


def _sibling_names(tree: ast.Module) -> dict[str, set[str]]:
    def exports(module: str) -> set[str]:
        return _exported_names(module) if (COMPONENT / f'{module}.py').is_file() else set()

    return _sibling_imports(tree, exports)


def test_no_module_calls_a_sibling_helper_it_never_imported():
    """No module may use a name its sibling defines unless it binds that name.

    Regression guard: dropping `from .game_batches import normalize_counts`
    left the whole suite green, because coordinator.py needs Home Assistant to
    import and `compileall` only checks syntax. The integration then failed to
    set up with `NameError: name 'normalize_counts' is not defined`.

    Every sibling module is inspected, not only the ones already imported, so a
    wholly missing import statement is caught as well as a partial one.
    """
    siblings = {
        path.stem: _exported_names(path.stem)
        for path in MODULES
        if path.stem != '__init__'
    }
    unresolved: dict[str, dict[str, set[str]]] = {}
    for path in MODULES:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        referenced = _referenced_names(tree)
        bound = _own_bindings(tree, lambda module: siblings.get(module, set())) | BUILTINS
        gaps = {
            module: used
            for module, exports in siblings.items()
            if (used := (referenced & exports) - bound)
        }
        if gaps:
            unresolved[path.name] = gaps
    assert not unresolved, unresolved


def test_the_game_batch_helpers_the_coordinator_uses_are_imported():
    """Pin the exact wiring this feature depends on."""
    coordinator = _tree('coordinator')
    imported = _sibling_imports(coordinator, _exported_names)['game_batches']
    used = _referenced_names(coordinator) & _exported_names('game_batches')
    assert used == {'normalize_counts', 'requested_count'}
    assert used <= imported, f'missing import: {sorted(used - imported)}'


def test_each_batch_consumer_imports_exactly_what_it_calls():
    """A stale or over-broad batch import is a bug, not a style preference."""
    for module, expected in (
        ('coordinator', {'normalize_counts', 'requested_count'}),
        ('service_runtime', {'merge_batches', 'next_batch', 'shortfalls'}),
    ):
        imported = _sibling_imports(_tree(module), _exported_names)['game_batches']
        assert imported == expected, module
    # The formula entity reads the counts through the coordinator, not directly.
    assert 'game_batches' not in _sibling_imports(_tree('sensor'), _exported_names)
