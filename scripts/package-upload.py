#!/usr/bin/env python3
"""Build a deterministic, database-free file-manager upload using the stdlib."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent.parent

# Keep this explicit: adding a repository file must never silently publish it.
APPROVED_FILES = (
    ".htaccess",
    "index.php",
    "README.md",
    "config/.htaccess",
    "config/config.php",
    "config/db.php",
    "database/.htaccess",
    "database/.gitkeep",
    "docs/.htaccess",
    "docs/API.md",
    "docs/UPLOAD.md",
    "lang/.htaccess",
    "lang/en.php",
    "lang/ru.php",
    "lang/uz.php",
    "public/.htaccess",
    "public/index.php",
    "public/api.php",
    "public/i18n.php",
    "public/assets/app.css",
    "public/assets/app.js",
    "public/assets/vendor/chart.umd.min.js",
    "public/assets/vendor/lucide.min.js",
    "public/assets/vendor/README.md",
    "public/assets/vendor/LICENSE-chartjs",
    "public/assets/vendor/LICENSE-lucide",
    "scripts/.htaccess",
    "scripts/process-recurring.php",
    "src/.htaccess",
    "src/Auth.php",
    "src/Database.php",
    "src/DemoData.php",
    "src/Finance.php",
    "src/Helpers.php",
    "src/Hosting.php",
    "src/Reports.php",
    "tests/.htaccess",
)


def approved_sources() -> list[tuple[str, bytes]]:
    sources = []
    for name in APPROVED_FILES:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe archive entry: {name}")
        current = ROOT
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"Refusing to package a symbolic link: {name}")
        if not current.is_file():
            raise ValueError(f"Required upload file is missing: {name}")
        sources.append((name, current.read_bytes()))
    if len(sources) != len({name for name, _ in sources}):
        raise ValueError("The upload allowlist contains duplicate entries.")
    return sources


def build(destination: Path) -> Path:
    destination = destination.expanduser()
    if destination.is_symlink():
        raise ValueError("The output ZIP must not be a symbolic link.")
    destination = destination.resolve()
    if destination.suffix.lower() != ".zip":
        raise ValueError("The output filename must end in .zip.")
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError("Write the upload ZIP outside the source checkout, for example /tmp/vela-upload.zip.")
    sources = approved_sources()
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=".vela-upload-", suffix=".zip", dir=destination.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, content in sources:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content, compresslevel=9)
        with zipfile.ZipFile(temporary) as archive:
            if archive.namelist() != list(APPROVED_FILES):
                raise ValueError("The upload archive does not match its approved file list.")
            failed = archive.testzip()
            if failed:
                raise ValueError(f"Archive integrity check failed: {failed}")
            for name in archive.namelist():
                parts = Path(name).parts
                if any(part in {".git", "__pycache__", ".runtime"} for part in parts):
                    raise ValueError(f"Private runtime content found in archive: {name}")
                filename = parts[-1].lower()
                if filename.startswith(".env") or ".db" in filename or ".sqlite" in filename:
                    raise ValueError(f"Private data found in archive: {name}")
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=Path(tempfile.gettempdir()) / "vela-upload.zip")
    arguments = parser.parse_args()
    try:
        destination = build(arguments.output)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"Upload packaging failed: {error}", file=sys.stderr)
        return 1
    print(f"Created {destination} ({destination.stat().st_size:,} bytes; {len(APPROVED_FILES)} approved files).")
    print("Extract its contents into the website folder. Existing financial databases are excluded and preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
