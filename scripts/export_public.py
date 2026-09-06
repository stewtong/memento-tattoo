from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Iterable, Optional


PUBLIC_ENTRIES = (
    ".github",
    "scripts",
    "src",
    "tests",
    "examples",
    "docs",
    "templates",
    ".gitignore",
    "README.md",
    "MEMENTO-PATTERN.md",
    "LICENSE",
    "pyproject.toml",
    "MANIFEST.in",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
)


def export_public(destination: Path, *, source_root: Optional[Path] = None) -> set[str]:
    source = (source_root or Path(__file__).resolve().parents[1]).resolve()
    if destination.is_symlink():
        raise ValueError("destination must not be a symlink")
    destination = destination.resolve()
    if destination == source or destination in source.parents or source in destination.parents:
        raise ValueError("destination must be separate from source root and its ancestors and descendants")
    if destination.exists():
        raise FileExistsError("export destination already exists; choose a new directory")

    # Validate the full source before creating an export. Following a link could
    # copy private material from outside the selected public surface.
    for entry in PUBLIC_ENTRIES:
        src = source / entry
        if not src.exists():
            raise FileNotFoundError(src)
        for path in [src, *src.rglob("*")]:
            if path.is_symlink():
                raise ValueError(f"public source contains a symlink: {path.relative_to(source)}")
    destination.mkdir(parents=True)

    copied: set[str] = set()
    for entry in PUBLIC_ENTRIES:
        src = source / entry
        if not src.exists():
            raise FileNotFoundError(src)
        dst = destination / entry
        if src.is_dir():
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info", "memory-layer-judgment-spec.md"),
            )
            copied.update(_relative_files(dst, destination))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.add(entry)
    return copied


def _relative_files(root: Path, base: Path) -> Iterable[str]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path.relative_to(base).as_posix()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export the public memento-tattoo GitHub project surface.")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--source-root", type=Path, default=None)
    args = parser.parse_args(argv)

    copied = export_public(args.destination, source_root=args.source_root)
    print(f"exported {len(copied)} files to {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
