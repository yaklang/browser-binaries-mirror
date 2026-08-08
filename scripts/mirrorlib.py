#!/usr/bin/env python3
"""Shared Chrome for Testing mirror data-contract helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PLATFORMS = (
    ("mac-arm64", "macos", "arm64"),
    ("mac-x64", "macos", "x64"),
    ("win64", "windows", "x64"),
    ("linux64", "linux", "x64"),
)
SOURCE_MANIFEST_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "last-known-good-versions-with-downloads.json"
)
KNOWN_GOOD_MANIFEST_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "known-good-versions-with-downloads.json"
)
PRODUCT_PREFIX = "/browsers/chrome"


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def write_json(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_key(version: str) -> tuple[int, int, int, int]:
    if not VERSION_RE.fullmatch(version):
        raise ValueError(f"invalid four-part Chrome version: {version!r}")
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def artifact_url(public_base_url: str, version: str, filename: str) -> str:
    return f"{public_base_url.rstrip('/')}{PRODUCT_PREFIX}/{version}/{filename}"


def validate_release_entry(entry: dict[str, Any]) -> None:
    version = entry.get("version")
    version_key(version)
    if entry.get("channel") != "stable":
        raise ValueError("release channel must be stable")
    if not isinstance(entry.get("revision"), str) or not entry["revision"].isdigit():
        raise ValueError("release revision must be a decimal string")
    artifacts = entry.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(PLATFORMS):
        raise ValueError(f"release must contain exactly {len(PLATFORMS)} artifacts")
    expected_pairs = {(os_name, arch) for _, os_name, arch in PLATFORMS}
    seen: set[tuple[str, str, str]] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("artifact must be an object")
        key = (artifact.get("os"), artifact.get("arch"), artifact.get("format"))
        if key in seen:
            raise ValueError(f"duplicate artifact tuple: {key}")
        seen.add(key)
        if key[:2] not in expected_pairs or key[2] != "zip":
            raise ValueError(f"unexpected artifact tuple: {key}")
        filename = artifact.get("filename")
        expected = f"chrome-cft-{version}-{key[0]}-{key[1]}.zip"
        if filename != expected:
            raise ValueError(f"unexpected artifact filename: {filename!r}, expected {expected!r}")
        if artifact.get("checksum_url") != f"{artifact.get('url')}.sha256.txt":
            raise ValueError(f"checksum URL does not match artifact URL for {filename}")
        expected_path = f"{PRODUCT_PREFIX}/{version}/{filename}"
        if urlparse(str(artifact.get("url"))).path != expected_path:
            raise ValueError(f"artifact URL path does not match contract for {filename}")
        if urlparse(str(artifact.get("checksum_url"))).path != f"{expected_path}.sha256.txt":
            raise ValueError(f"checksum URL path does not match contract for {filename}")
        if artifact.get("signature", "missing") is not None:
            raise ValueError(f"signature must be null for {filename}")
        if not SHA256_RE.fullmatch(str(artifact.get("sha256", ""))):
            raise ValueError(f"invalid SHA-256 for {filename}")
        if not isinstance(artifact.get("size"), int) or artifact["size"] <= 0:
            raise ValueError(f"invalid size for {filename}")
        source_url = artifact.get("source_url")
        parsed = urlparse(str(source_url))
        if parsed.scheme != "https" or parsed.netloc != "storage.googleapis.com":
            raise ValueError(f"non-official source URL for {filename}: {source_url!r}")


def validate_manifest(manifest: dict[str, Any]) -> None:
    required_top = {
        "schema_version",
        "product",
        "channel",
        "generated_at",
        "source",
        "max_versions",
        "latest",
        "versions",
    }
    if set(manifest) != required_top:
        raise ValueError(f"manifest keys differ from contract: {sorted(set(manifest) ^ required_top)}")
    if manifest["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    if manifest["product"] != "chrome-for-testing" or manifest["channel"] != "stable":
        raise ValueError("manifest product/channel mismatch")
    source = manifest["source"]
    if source != {"name": "Google Chrome for Testing", "manifest_url": SOURCE_MANIFEST_URL}:
        raise ValueError("manifest source metadata mismatch")
    max_versions = manifest["max_versions"]
    versions = manifest["versions"]
    if not isinstance(max_versions, int) or max_versions < 1:
        raise ValueError("max_versions must be a positive integer")
    if not isinstance(versions, list) or not 1 <= len(versions) <= max_versions:
        raise ValueError("versions must contain between 1 and max_versions entries")
    version_names = [entry.get("version") for entry in versions]
    if version_names != sorted(version_names, key=version_key, reverse=True):
        raise ValueError("versions are not in descending numeric order")
    if len(version_names) != len(set(version_names)):
        raise ValueError("manifest contains duplicate versions")
    if manifest["latest"] != version_names[0]:
        raise ValueError("latest must equal versions[0].version")
    for entry in versions:
        validate_release_entry(entry)


def load_schema_and_validate(manifest: dict[str, Any], schema_path: str | Path) -> None:
    validate_manifest(manifest)
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - guarded by CI requirements install
        raise RuntimeError("jsonschema is required for schema validation") from exc
    jsonschema.Draft202012Validator(
        load_json(schema_path), format_checker=jsonschema.FormatChecker()
    ).validate(manifest)
