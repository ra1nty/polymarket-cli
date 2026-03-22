from __future__ import annotations

import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import tomllib
from typing import Iterable
import zipfile


ROOT = Path(__file__).resolve().parent
PYPROJECT = ROOT / "pyproject.toml"


def _load_project() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["project"]


def _dist_name(name: str) -> str:
    return name.replace("-", "_")


def _wheel_filename(name: str, version: str) -> str:
    return f"{_dist_name(name)}-{version}-py3-none-any.whl"


def _metadata_text(project: dict) -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {project['name']}",
        f"Version: {project['version']}",
        f"Summary: {project['description']}",
    ]
    if project.get("requires-python"):
        lines.append(f"Requires-Python: {project['requires-python']}")
    for author in project.get("authors", []):
        name = author.get("name")
        email = author.get("email")
        if name and email:
            lines.append(f"Author-email: {name} <{email}>")
        elif email:
            lines.append(f"Author-email: {email}")
        elif name:
            lines.append(f"Author: {name}")
    license_info = project.get("license", {})
    if isinstance(license_info, dict) and license_info.get("text"):
        lines.append(f"License: {license_info['text']}")
    return "\n".join(lines) + "\n"


def _entry_points_text(project: dict) -> str:
    scripts = project.get("scripts", {})
    if not scripts:
        return ""
    lines = ["[console_scripts]"]
    lines.extend(f"{name} = {target}" for name, target in scripts.items())
    return "\n".join(lines) + "\n"


def _iter_package_files() -> Iterable[tuple[Path, str]]:
    package_dir = ROOT / "polymarket_clob_agent"
    for path in sorted(package_dir.rglob("*")):
        if path.is_file():
            yield path, path.relative_to(ROOT).as_posix()


def _record_row(relpath: str, content: bytes) -> list[str]:
    digest = hashlib.sha256(content).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return [relpath, f"sha256={encoded}", str(len(content))]


def _build_wheel(
    wheel_directory: str, *,
    editable: bool,
    metadata_directory: str | None = None,
) -> str:
    project = _load_project()
    name = project["name"]
    version = project["version"]
    dist_name = _dist_name(name)
    dist_info = f"{dist_name}-{version}.dist-info"
    wheel_name = _wheel_filename(name, version)
    output_path = Path(wheel_directory) / wheel_name

    os.makedirs(wheel_directory, exist_ok=True)

    entries: list[tuple[str, bytes]] = []
    if editable:
        pth_name = f"{dist_name}.pth"
        entries.append((pth_name, (str(ROOT) + "\n").encode("utf-8")))
    else:
        entries.extend((relpath, path.read_bytes()) for path, relpath in _iter_package_files())

    metadata = _metadata_text(project).encode("utf-8")
    wheel = (
        "Wheel-Version: 1.0\n"
        "Generator: build_backend\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")
    entry_points = _entry_points_text(project).encode("utf-8")

    entries.append((f"{dist_info}/METADATA", metadata))
    entries.append((f"{dist_info}/WHEEL", wheel))
    if entry_points:
        entries.append((f"{dist_info}/entry_points.txt", entry_points))

    record_rows = [_record_row(relpath, content) for relpath, content in entries]
    record_path = f"{dist_info}/RECORD"
    with output_path.open("wb") as raw:
        with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for relpath, content in entries:
                zf.writestr(relpath, content)

            record_io = io.StringIO()
            writer = csv.writer(record_io, lineterminator="\n")
            writer.writerows(record_rows)
            writer.writerow([record_path, "", ""])
            zf.writestr(record_path, record_io.getvalue().encode("utf-8"))

    return wheel_name


def build_wheel(
    wheel_directory: str,
    config_settings: dict | None = None,
    metadata_directory: str | None = None,
) -> str:
    del config_settings, metadata_directory
    return _build_wheel(wheel_directory, editable=False)


def build_editable(
    wheel_directory: str,
    config_settings: dict | None = None,
    metadata_directory: str | None = None,
) -> str:
    del config_settings, metadata_directory
    return _build_wheel(wheel_directory, editable=True)


def get_requires_for_build_wheel(config_settings: dict | None = None) -> list[str]:
    del config_settings
    return []


def get_requires_for_build_editable(config_settings: dict | None = None) -> list[str]:
    del config_settings
    return []


def prepare_metadata_for_build_wheel(
    metadata_directory: str,
    config_settings: dict | None = None,
) -> str:
    del config_settings
    return _prepare_metadata(metadata_directory)


def prepare_metadata_for_build_editable(
    metadata_directory: str,
    config_settings: dict | None = None,
) -> str:
    del config_settings
    return _prepare_metadata(metadata_directory)


def _prepare_metadata(metadata_directory: str) -> str:
    project = _load_project()
    dist_info = f"{_dist_name(project['name'])}-{project['version']}.dist-info"
    output_dir = Path(metadata_directory) / dist_info
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "METADATA").write_text(_metadata_text(project), encoding="utf-8")
    entry_points = _entry_points_text(project)
    if entry_points:
        (output_dir / "entry_points.txt").write_text(entry_points, encoding="utf-8")
    (output_dir / "WHEEL").write_text(
        "Wheel-Version: 1.0\n"
        "Generator: build_backend\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n",
        encoding="utf-8",
    )
    return dist_info
