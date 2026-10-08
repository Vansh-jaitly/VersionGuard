"""Build documentation entries from the libraries that are actually installed.

The documentation store is not downloaded from the web. It is read out of the
installed library itself: for every public function, class and method this
records its name, signature and the first part of its docstring. That makes
the store exactly match the pinned version, and it works offline.

IMPORTANT: this file runs INSIDE the pinned environments (some are Python
3.7), so it uses only the standard library and Python 3.7 syntax. Do not add
third-party imports or newer syntax here.

Usage (inside an environment):
    python apidocs.py --dist flask --dist werkzeug --out flask.jsonl
    python apidocs.py --module numpy --out numpy.jsonl
"""

import argparse
import collections
import importlib
import inspect
import json
import pkgutil
import re
import sys
import warnings

SKIP_NAMES = {"tests", "test", "conftest", "setup", "distutils", "f2py", "__main__"}
MAX_CLASS_MEMBERS = 300
DOC_LIMIT = 500


def dist_version(dist_name):
    try:
        from importlib import metadata as md  # Python 3.8+

        return md.version(dist_name)
    except Exception:
        pass
    try:
        import pkg_resources  # Python 3.7 fallback

        return pkg_resources.get_distribution(dist_name).version
    except Exception:
        return None


def top_level_modules(dist_name):
    """Import names provided by an installed distribution (e.g. Pillow -> PIL)."""
    names = []
    try:
        from importlib import metadata as md

        dist = md.distribution(dist_name)
        text = dist.read_text("top_level.txt")
        if text:
            names = [line.strip() for line in text.splitlines() if line.strip()]
        elif dist.files:
            seen = []
            for path in dist.files:
                parts = str(path).replace("\\", "/").split("/")
                if len(parts) > 1 and parts[1] == "__init__.py" and parts[0] not in seen:
                    seen.append(parts[0])
            names = seen
    except Exception:
        try:
            import pkg_resources

            text = pkg_resources.get_distribution(dist_name).get_metadata("top_level.txt")
            names = [line.strip() for line in text.splitlines() if line.strip()]
        except Exception:
            names = []
    names = [n for n in names if n and not n.startswith("_")]
    if not names:
        names = [dist_name.replace("-", "_")]
    return names


def _belongs(obj, root):
    module = getattr(obj, "__module__", None)
    if not isinstance(module, str):
        return True
    return module == root or module.startswith(root + ".")


def _signature(obj):
    try:
        return str(inspect.signature(obj))
    except Exception:
        return ""


def _short_doc(obj, name):
    """(signature_from_doc, text): first part of the docstring, flattened."""
    try:
        doc = inspect.getdoc(obj) or ""
    except Exception:
        doc = ""
    if not doc:
        return "", ""
    lines = doc.strip().splitlines()
    sig_from_doc = ""
    short = name.rsplit(".", 1)[-1]
    # Builtins often put the signature on the first docstring line.
    if lines and re.match(r"^%s\(.*\)" % re.escape(short), lines[0].strip()):
        sig_from_doc = lines[0].strip()[len(short):]
        lines = lines[1:]
    text = " ".join(part.strip() for part in lines if part.strip())
    text = re.sub(r"\s+", " ", text)
    if len(text) > DOC_LIMIT:
        cut = text.rfind(" ", 0, DOC_LIMIT)
        text = text[: cut if cut > 0 else DOC_LIMIT] + " ..."
    return sig_from_doc, text


def _entry(qualname, kind, obj, library, version):
    sig_from_doc, doc = _short_doc(obj, qualname)
    signature = _signature(obj) or sig_from_doc
    return {
        "qualname": qualname,
        "kind": kind,
        "signature": signature,
        "doc": doc,
        "library": library,
        "version": version,
    }


def _public_names(module, with_submodules):
    """(names to visit, names the module explicitly exports, whether it has __all__).

    __all__ is trusted for which SUB-MODULES are public (this keeps internals
    such as pandas.core out of the store), but it is often incomplete for
    functions, so public-looking names from dir() are visited as well.
    """
    declared = getattr(module, "__all__", None)
    has_all = bool(
        isinstance(declared, (list, tuple)) and declared and all(isinstance(n, str) for n in declared)
    )
    exported = set(declared) if has_all else set()
    names = list(declared) if has_all else []
    try:
        listed = dir(module)
    except Exception:
        listed = []
    for name in listed:
        if not name.startswith("_") and name not in exported:
            names.append(name)
    if with_submodules and not has_all and hasattr(module, "__path__"):
        try:
            for info in pkgutil.iter_modules(module.__path__):
                sub = info.name
                if not sub.startswith("_") and sub not in SKIP_NAMES and sub not in names:
                    names.append(sub)
        except Exception:
            pass
    return names, exported, has_all


def _defined_in_package(cls, member, root):
    for base in getattr(cls, "__mro__", ()):
        if member in vars(base):
            return _belongs(base, root)
    return False


def _class_members(cls, qualname, root, library, version):
    out = []
    try:
        names = sorted(n for n in dir(cls) if not n.startswith("_"))
    except Exception:
        return out
    for name in names:
        if len(out) >= MAX_CLASS_MEMBERS:
            break
        if not _defined_in_package(cls, name, root):
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                member = getattr(cls, name)
        except Exception:
            continue
        kind = "method" if callable(member) else "attribute"
        entry = _entry(qualname + "." + name, kind, member, library, version)
        if kind == "attribute" and not entry["doc"]:
            continue  # an undocumented constant adds noise to the lookup
        out.append(entry)
    return out


def walk(root_name, library=None, version=None, max_entries=12000, max_depth=2):
    """Breadth-first walk of a package's public API. Returns a list of entries."""
    library = library or root_name
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        root = importlib.import_module(root_name)
    seen_modules = {id(root)}
    seen_objects = set()
    entries = []
    queue = collections.deque([(root, root_name, 0)])
    while queue and len(entries) < max_entries:
        module, path, depth = queue.popleft()
        names, exported, has_all = _public_names(module, with_submodules=depth < max_depth)
        for name in names:
            if len(entries) >= max_entries:
                break
            qualname = path + "." + name
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        obj = getattr(module, name)
                    except AttributeError:
                        obj = importlib.import_module(qualname)
            except Exception:
                continue
            if inspect.ismodule(obj):
                if has_all and name not in exported:
                    continue  # a sub-module the package did not declare public
                real = getattr(obj, "__name__", "")
                inside = real == root_name or real.startswith(root_name + ".")
                if (
                    inside
                    and id(obj) not in seen_modules
                    and depth + 1 <= max_depth
                    and name not in SKIP_NAMES
                ):
                    seen_modules.add(id(obj))
                    queue.append((obj, qualname, depth + 1))
                continue
            if name not in exported:
                # Not explicitly exported: the root package may re-export freely
                # (flask.Flask), but deeper modules only count for what they
                # define themselves. Otherwise a helper imported into some
                # internal module is recorded under that misleading path.
                home = root_name if depth == 0 else getattr(module, "__name__", path)
                if not _belongs(obj, home):
                    continue
            if inspect.isclass(obj):
                if id(obj) in seen_objects:
                    continue
                seen_objects.add(id(obj))
                entries.append(_entry(qualname, "class", obj, library, version))
                entries.extend(_class_members(obj, qualname, root_name, library, version))
            elif callable(obj):
                if id(obj) in seen_objects:
                    continue
                seen_objects.add(id(obj))
                entries.append(_entry(qualname, "function", obj, library, version))
    return entries[:max_entries]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", action="append", default=[], help="installed distribution name")
    parser.add_argument("--module", action="append", default=[], help="import name")
    parser.add_argument("--out", default="-", help="output JSONL path, or - for stdout")
    parser.add_argument("--max-entries", type=int, default=12000)
    parser.add_argument("--max-depth", type=int, default=2)
    args = parser.parse_args(argv)

    targets = []  # (module name, library label, version)
    for dist in args.dist:
        version = dist_version(dist)
        for module in top_level_modules(dist):
            targets.append((module, dist, version))
    for module in args.module:
        targets.append((module, module, dist_version(module)))

    entries = []
    problems = []
    for module, library, version in targets:
        try:
            found = walk(module, library, version, args.max_entries, args.max_depth)
            entries.extend(found)
        except Exception as exc:  # the caller needs to know which library failed
            problems.append("%s: %s: %s" % (module, type(exc).__name__, exc))

    stream = sys.stdout if args.out == "-" else open(args.out, "w", encoding="utf-8")
    try:
        for entry in entries:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    finally:
        if stream is not sys.stdout:
            stream.close()
    for problem in problems:
        sys.stderr.write("apidocs: could not walk " + problem + "\n")
    sys.stderr.write("apidocs: wrote %d entries\n" % len(entries))
    return 0 if entries else 1


if __name__ == "__main__":
    sys.exit(main())
