"""The guard: flag calls that do not exist in the INSTALLED library versions.

    python -m versionguard.check path/to/file.py [more paths ...]

It parses each file, follows names back to their imports, and looks every
`module.attribute` chain up in the libraries installed in the current
environment (which, in CI, are the versions the project pins).

    VG001  the attribute does not exist in the installed version   (error)
    VG002  the keyword argument does not exist in the installed version (error)
    VG003  the module is not installed                              (error)
    VG004  the attribute is deprecated in the installed version     (warning)

Exit code 1 if there is at least one error (or any finding with --strict).

Known limit: it follows names, not values. `df.append(...)` on a variable is
invisible to it (the type of `df` is unknown); `pd.DataFrame.append` is not.
The repair round covers what only shows up at run time.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import functools
import importlib
import importlib.util
import inspect
import json
import sys
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

ERROR, WARNING = "error", "warning"
_MISSING = object()


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    col: int
    code: str
    level: str
    symbol: str
    message: str

    def render(self) -> str:
        return f"{self.file}:{self.line}:{self.col}: {self.code} {self.message}"

    def github(self) -> str:
        message = self.message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        filename = self.file.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        filename = filename.replace(":", "%3A").replace(",", "%2C")
        return f"::{self.level} file={filename},line={self.line},col={self.col},title={self.code}::{message}"


def _stdlib_names() -> frozenset[str]:
    names = getattr(sys, "stdlib_module_names", None)
    return frozenset(names) if names else frozenset(sys.builtin_module_names)


STDLIB = _stdlib_names()


@functools.lru_cache(maxsize=1)
def _distributions() -> dict[str, list[str]]:
    try:
        from importlib import metadata

        return dict(metadata.packages_distributions())
    except Exception:  # noqa: BLE001
        return {}


@functools.lru_cache(maxsize=None)
def _version_of(root: str) -> str:
    """'pandas 2.0.3' for the message; falls back to just the name."""
    try:
        from importlib import metadata

        for dist in _distributions().get(root, []):
            return f"{dist} {metadata.version(dist)}"
        return f"{root} {metadata.version(root)}"
    except Exception:  # noqa: BLE001 - version is only for the message
        module = sys.modules.get(root)
        version = getattr(module, "__version__", None)
        return f"{root} {version}" if version else root


def _suggest(owner: Any, name: str) -> str:
    try:
        candidates = [n for n in dir(owner) if not n.startswith("_")]
    except Exception:  # noqa: BLE001
        return ""
    close = difflib.get_close_matches(name, candidates, n=2, cutoff=0.6)
    return f" Did you mean {' or '.join(repr(c) for c in close)}?" if close else ""


class _Resolver:
    """Looks dotted names up in the installed libraries, with a cache."""

    def __init__(self) -> None:
        self._modules: dict[str, Any] = {}

    def module(self, name: str) -> Any:
        if name not in self._modules:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    self._modules[name] = importlib.import_module(name)
            except Exception as exc:  # noqa: BLE001 - any import failure means "not usable"
                self._modules[name] = exc
        return self._modules[name]

    @staticmethod
    def _exists(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except Exception:  # noqa: BLE001 - parent missing or broken finder
            return False

    def resolve(self, dotted: str) -> tuple[Any, str, str, list[str]]:
        """Follow a dotted name as far as it can be trusted.

        Returns (object, status, detail, deprecations) where status is:
          ok              fully resolved, object is the target
          unknown         stopped early (value of unknown type); nothing to report
          missing_module  the top-level module is not installed; detail = name
          missing         detail = "owner|attribute|library message"
        """
        parts = dotted.split(".")
        current = self.module(parts[0])
        if isinstance(current, Exception):
            return None, "missing_module", parts[0], []
        deprecations: list[str] = []
        path = parts[0]
        for part in parts[1:]:
            if not (inspect.ismodule(current) or inspect.isclass(current)):
                return None, "unknown", "", deprecations
            hint = ""
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    nxt = getattr(current, part)
                except AttributeError as exc:
                    nxt = _MISSING
                    hint = str(exc).strip().splitlines()[0][:200] if str(exc).strip() else ""
                except Exception:  # noqa: BLE001 - a lazy attribute that fails to load
                    return None, "unknown", "", deprecations
            for warning in caught:
                if issubclass(warning.category, (DeprecationWarning, FutureWarning)):
                    deprecations.append(f"{path}.{part}|{str(warning.message).splitlines()[0][:200]}")
            if nxt is _MISSING and inspect.ismodule(current):
                sub = self.module(f"{path}.{part}")
                if not isinstance(sub, Exception):
                    nxt = sub
                elif self._exists(f"{path}.{part}"):
                    # The submodule is there but needs something that is not
                    # installed (an optional dependency). Not our call.
                    return None, "unknown", "", deprecations
            if nxt is _MISSING:
                return current, "missing", f"{path}|{part}|{hint}", deprecations
            current = nxt
            path = f"{path}.{part}"
        return current, "ok", "", deprecations


def _chain(node: ast.AST) -> Optional[list[str]]:
    """['np', 'linalg', 'norm'] for np.linalg.norm; None if not a pure name chain."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        parts.append(node.id)
        return parts[::-1]
    return None


def _rebound_names(tree: ast.AST) -> set[str]:
    """Names assigned somewhere in the file; an import alias that is also
    assigned to cannot be trusted, so it is skipped."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
    return names


def _is_local(root: str, search_dirs: Iterable[Path]) -> bool:
    for directory in search_dirs:
        if (directory / f"{root}.py").is_file() or (directory / root).is_dir():
            return True
    return False


_TOLERANT_EXCEPTIONS = {"ImportError", "ModuleNotFoundError", "AttributeError", "Exception", "BaseException"}
PLAIN, CONDITIONAL, GUARDED, TYPE_ONLY = "plain", "conditional", "guarded", "type_only"


def _mentions_type_checking(test: ast.AST) -> bool:
    for node in ast.walk(test):
        if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING":
            return True
    return False


def _handler_tolerates(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    kinds = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    for kind in kinds:
        name = kind.attr if isinstance(kind, ast.Attribute) else getattr(kind, "id", "")
        if name in _TOLERANT_EXCEPTIONS:
            return True
    return False


class _Contexts:
    """Where a node sits: code that always runs, code behind a condition, code
    whose failure is already handled, or code only a type checker reads."""

    def __init__(self, tree: ast.AST) -> None:
        self._parent: dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self._parent[id(child)] = node

    def of(self, node: ast.AST, is_import: bool = False) -> str:
        result = PLAIN
        child = node
        parent = self._parent.get(id(child))
        while parent is not None:
            if (
                (isinstance(parent, (ast.arg, ast.AnnAssign)) and child is parent.annotation)
                or (isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is parent.returns)
            ):
                return TYPE_ONLY  # annotations are for type checkers
            if isinstance(parent, ast.If):
                if _mentions_type_checking(parent.test) and child in parent.body:
                    return TYPE_ONLY
                if child is not parent.test:
                    result = CONDITIONAL
            elif isinstance(parent, ast.Try):
                if child in parent.body and any(_handler_tolerates(h) for h in parent.handlers):
                    return GUARDED
            elif isinstance(parent, ast.ExceptHandler):
                result = CONDITIONAL
            elif is_import and isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result = CONDITIONAL  # a lazy import of an optional dependency
            child = parent
            parent = self._parent.get(id(child))
        return result


def _positive_probes(test: ast.AST) -> set[tuple[str, str]]:
    """Attributes guaranteed present when this condition evaluates as true."""
    if isinstance(test, ast.BoolOp):
        probes = [_positive_probes(value) for value in test.values]
        return set.union(*probes) if isinstance(test.op, ast.And) else set.intersection(*probes)
    if (isinstance(test, ast.Call) and isinstance(test.func, ast.Name)
            and test.func.id in {"hasattr", "getattr"} and len(test.args) >= 2
            and isinstance(test.args[1], ast.Constant) and isinstance(test.args[1].value, str)):
        if test.func.id == "getattr" and len(test.args) >= 3:
            default = test.args[2]
            if not isinstance(default, ast.Constant) or bool(default.value):
                return set()
        owner = _chain(test.args[0])
        if owner:
            return {(".".join(owner), test.args[1].value)}
    return set()


def _is_probed(node: ast.AST, symbol: str, aliases: dict[str, str], contexts: _Contexts) -> bool:
    child = node
    parent = contexts._parent.get(id(child))
    while parent is not None:
        if isinstance(parent, ast.If) and child in parent.body:
            for owner, attribute in _positive_probes(parent.test):
                root, *rest = owner.split(".")
                resolved_owner = ".".join([aliases.get(root, root), *rest])
                if f"{resolved_owner}.{attribute}" == symbol:
                    return True
        child = parent
        parent = contexts._parent.get(id(child))
    return False


def _keywords_checkable(target: Any) -> bool:
    """Only check keyword arguments where the signature can be trusted.

    Skipped: functions written in C (their text signatures are often
    incomplete), and anything that really takes **kwargs, whatever signature it
    advertises (decorators accept extra or renamed arguments, then set
    __signature__).
    """
    if inspect.isclass(target):
        candidates = [getattr(target, "__init__", None), getattr(target, "__new__", None)]
        candidates = [c for c in candidates if getattr(c, "__code__", None) is not None]
        if not candidates:
            return False
    else:
        candidates = [target]
    for candidate in candidates:
        code = getattr(candidate, "__code__", None)
        if code is None or code.co_flags & inspect.CO_VARKEYWORDS:
            return False
    return True


def check_source(
    source: str,
    filename: str = "<string>",
    search_dirs: Iterable[Path] = (),
    resolver: Optional[_Resolver] = None,
) -> list[Finding]:
    """All findings for one file's source text."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return [
            Finding(filename, exc.lineno or 1, exc.offset or 0, "VG000", ERROR, "", f"syntax error: {exc.msg}")
        ]
    resolver = resolver or _Resolver()
    search_dirs = list(search_dirs)
    contexts = _Contexts(tree)
    findings: list[Finding] = []
    seen: set[tuple[int, int, str, str]] = set()
    missing_modules: set[str] = set()

    def report(node: ast.AST, code: str, level: str, symbol: str, message: str) -> None:
        key = (getattr(node, "lineno", 1), getattr(node, "col_offset", 0), code, symbol)
        if key not in seen:
            seen.add(key)
            findings.append(Finding(filename, key[0], key[1] + 1, code, level, symbol, message))

    def third_party(dotted: str) -> bool:
        root = dotted.split(".")[0]
        return bool(root) and root not in STDLIB and not _is_local(root, search_dirs)

    def report_resolution(node: ast.AST, dotted: str, context: str) -> tuple[Any, str]:
        """Resolve `dotted` and report problems. Returns (object or None, status)."""
        obj, status, detail, deprecations = resolver.resolve(dotted)
        if context in (GUARDED, TYPE_ONLY):
            return (obj if status == "ok" else None), status
        level = ERROR if context == PLAIN else WARNING
        root = dotted.split(".")[0]
        for item in deprecations:
            symbol, text = item.split("|", 1)
            report(node, "VG004", WARNING, symbol, f"{symbol} is deprecated in {_version_of(root)}: {text}")
        if status == "missing_module":
            if detail not in missing_modules:  # once per file is enough
                missing_modules.add(detail)
                report(node, "VG003", level, detail, f"module '{detail}' is not installed in this environment")
        elif status == "missing":
            owner, attribute, hint = detail.split("|", 2)
            if not _is_probed(node, f"{owner}.{attribute}", aliases, contexts):
                message = f"'{owner}' has no attribute '{attribute}' in {_version_of(root)}."
                message += _suggest(obj, attribute)
                if hint and attribute in hint and "has no attribute" not in hint:
                    message += f" ({hint})"
                report(node, "VG001", level, f"{owner}.{attribute}", message)
        return (obj if status == "ok" else None), status

    # 1. Imports: build the alias table, and check `from x import y` right away.
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            context = contexts.of(node, is_import=True)
            if context == TYPE_ONLY:
                continue
            for alias in node.names:
                if not third_party(alias.name):
                    continue
                _obj, status = report_resolution(node, alias.name, context)
                if status != "missing_module":
                    if alias.asname:
                        aliases[alias.asname] = alias.name
                    else:
                        aliases[alias.name.split(".")[0]] = alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module or not third_party(node.module):
                continue
            context = contexts.of(node, is_import=True)
            if context == TYPE_ONLY:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                _obj, status = report_resolution(node, f"{node.module}.{alias.name}", context)
                if status in ("ok", "unknown"):
                    aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    for name in _rebound_names(tree):
        aliases.pop(name, None)
    if not aliases:
        findings.sort(key=lambda f: (f.line, f.col, f.code))
        return findings

    # 2. Attribute chains rooted at an imported name. Outermost chain only.
    inner: set[int] = set()
    resolved: dict[int, Any] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and id(node) not in inner:
            parts = _chain(node)
            child = node.value
            while isinstance(child, ast.Attribute):
                inner.add(id(child))
                child = child.value
            if parts and parts[0] in aliases:
                dotted = ".".join([aliases[parts[0]], *parts[1:]])
                resolved[id(node)], _status = report_resolution(node, dotted, contexts.of(node))

    # 3. Keyword arguments of calls whose target was fully resolved.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        context = contexts.of(node)
        if context in (GUARDED, TYPE_ONLY):
            continue
        func = node.func
        target = None
        dotted = ""
        if isinstance(func, ast.Attribute) and resolved.get(id(func)) is not None:
            target = resolved[id(func)]
            parts = _chain(func) or []
            dotted = ".".join([aliases[parts[0]], *parts[1:]]) if parts else ""
        elif isinstance(func, ast.Name) and func.id in aliases:
            dotted = aliases[func.id]
            target, status, _detail, _dep = resolver.resolve(dotted)
            if status != "ok":
                target = None
        if target is None or not callable(target) or not _keywords_checkable(target):
            continue
        try:
            # follow_wrapped=False: a decorator that accepts **kwargs may add or
            # rename arguments, so the wrapper's own signature is the safe one.
            parameters = list(inspect.signature(target, follow_wrapped=False).parameters.values())
        except (TypeError, ValueError):
            continue
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters):
            continue
        accepted = {
            p.name
            for p in parameters
            if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        }
        for keyword in node.keywords:
            if keyword.arg is None or keyword.arg in accepted:
                continue
            close = difflib.get_close_matches(keyword.arg, sorted(accepted), n=2, cutoff=0.6)
            if close:
                hint = f" Did you mean {' or '.join(repr(c) for c in close)}?"
            else:
                names = [p.name for p in parameters if p.name in accepted and p.name != "self"][:8]
                hint = f" Accepted arguments: {', '.join(names)}." if names else ""
            report(
                keyword.value,
                "VG002",
                ERROR if context == PLAIN else WARNING,
                f"{dotted}({keyword.arg}=)",
                f"'{dotted}' has no argument '{keyword.arg}' in {_version_of(dotted.split('.')[0])}.{hint}",
            )

    findings.sort(key=lambda f: (f.line, f.col, f.code))
    return findings


def iter_python_files(paths: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(
                p
                for p in sorted(path.rglob("*.py"))
                if not any(part.startswith(".") or part in {"venv", "node_modules", "__pycache__"} for part in p.parts)
            )
        elif path.suffix == ".py" and path.is_file():
            files.append(path)
    return files


def check_paths(paths: Iterable[str], root: Optional[Path] = None) -> list[Finding]:
    root = root or Path.cwd()
    resolver = _Resolver()
    findings: list[Finding] = []
    for path in iter_python_files(paths):
        source = path.read_text(encoding="utf-8", errors="replace")
        findings.extend(check_source(source, str(path), [root, path.parent], resolver))
    return findings


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("paths", nargs="+", help="Python files or folders to check")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--github", action="store_true", help="also print GitHub Actions annotations")
    parser.add_argument("--strict", action="store_true", help="warnings also fail the check")
    args = parser.parse_args(argv)

    invalid = [path for path in args.paths if not Path(path).exists()]
    if invalid:
        print(f"error: check path does not exist: {', '.join(invalid)}", file=sys.stderr)
        return 2
    if not iter_python_files(args.paths):
        print("error: no Python files found to check", file=sys.stderr)
        return 2

    findings = check_paths(args.paths)
    errors = [f for f in findings if f.level == ERROR]
    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        for finding in findings:
            print(finding.render())
            if args.github:
                print(finding.github())
        checked = len(iter_python_files(args.paths))
        warnings_count = len(findings) - len(errors)
        print(f"versionguard: {checked} file(s) checked, {len(errors)} error(s), {warnings_count} warning(s)")
    return 1 if errors or (args.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
