from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATED_PATH_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
}
ALLOWED_HIDDEN_FILES = {".env.example"}
TEXT_SUFFIXES = {"", ".example", ".ini", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}


def _is_generated_path(path: Path) -> bool:
    return any(
        part in GENERATED_PATH_PARTS
        or part.endswith(".egg-info")
        or (part.startswith(".") and part not in ALLOWED_HIDDEN_FILES)
        for part in path.parts
    )


def _read_text_or_skip(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _python_files(*relative_roots: str) -> list[Path]:
    files: list[Path] = []
    for relative_root in relative_roots:
        root = REPO_ROOT / relative_root
        files.extend(path for path in root.rglob("*.py") if not _is_generated_path(path))
    return sorted(files)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)

    return modules


def _has_import_with_prefix(module: str, forbidden_prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden_prefixes)


def _assert_no_forbidden_imports(
    relative_roots: tuple[str, ...], forbidden_prefixes: tuple[str, ...]
) -> None:
    violations: list[str] = []

    for path in _python_files(*relative_roots):
        for module in _imported_modules(path):
            if _has_import_with_prefix(module, forbidden_prefixes):
                violations.append(f"{path.relative_to(REPO_ROOT)} imports {module}")

    assert violations == []


def test_pipelines_do_not_import_backend_internals() -> None:
    _assert_no_forbidden_imports(("pipelines/src/pipelines",), ("app", "backend"))


def test_backend_does_not_import_pipelines() -> None:
    _assert_no_forbidden_imports(("backend/src/app", "backend/alembic"), ("pipelines",))


def test_shared_core_does_not_import_app_backend_or_pipelines() -> None:
    _assert_no_forbidden_imports(
        ("packages/shared_core/src/shared_core",),
        ("app", "backend", "pipelines"),
    )


def test_no_stale_apps_path_references() -> None:
    stale_path_marker = "apps" + "/"
    stale_import_marker = "apps" + "."
    searchable_roots = [
        REPO_ROOT / "backend",
        REPO_ROOT / "docs",
        REPO_ROOT / "frontend",
        REPO_ROOT / "packages",
        REPO_ROOT / "pipelines",
        REPO_ROOT / "README.md",
        REPO_ROOT / ".env.example",
    ]
    violations: list[str] = []

    for root in searchable_roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or _is_generated_path(path):
                continue
            if path.suffix not in TEXT_SUFFIXES:
                continue

            text = _read_text_or_skip(path)
            if text is None:
                continue
            if stale_path_marker in text or stale_import_marker in text:
                violations.append(str(path.relative_to(REPO_ROOT)))

    assert violations == []
