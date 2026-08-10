#!/usr/bin/env python3
"""Merge one complete release entry into the bounded public manifest."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from mirrorlib import SOURCE_MANIFEST_URL, load_json, validate_manifest, version_key, write_json


def comparable_entry(entry: dict) -> dict:
    return {key: value for key, value in entry.items() if key != "mirrored_at"}


def load_pinned_versions(path: str | Path) -> list[str]:
    config = load_json(path)
    items = config.get("versions")
    if not isinstance(items, list) or not items:
        raise ValueError("historical Stable config must contain a non-empty versions list")
    versions = []
    majors = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("historical Stable version must be an object")
        version = item.get("version")
        major = item.get("major")
        version_key(version)
        if not isinstance(major, int) or major != int(version.split(".", 1)[0]):
            raise ValueError(f"historical Stable major does not match version {version!r}")
        if version in versions or major in majors:
            raise ValueError("historical Stable config contains duplicate versions or majors")
        versions.append(version)
        majors.add(major)
    return versions


def build_manifest(
    entry: dict,
    existing: dict | None,
    max_versions: int,
    pinned_versions: list[str] | tuple[str, ...] = (),
) -> dict:
    if max_versions < 1:
        raise ValueError("max_versions must be at least 1")
    if len(set(pinned_versions)) != len(pinned_versions):
        raise ValueError("pinned_versions must be unique")
    for version in pinned_versions:
        version_key(version)
    if len(pinned_versions) >= max_versions:
        raise ValueError("max_versions must leave at least one slot beyond pinned versions")
    versions = [] if existing is None else list(existing.get("versions", []))
    same_version = [item for item in versions if item.get("version") == entry["version"]]
    if same_version:
        if len(same_version) != 1 or comparable_entry(same_version[0]) != comparable_entry(entry):
            raise ValueError(f"refusing to change published release metadata for {entry['version']}")
        entry = same_version[0]
    versions = [item for item in versions if item.get("version") != entry["version"]]
    versions.append(entry)
    versions.sort(key=lambda item: version_key(item["version"]), reverse=True)
    pinned = [item for item in versions if item["version"] in pinned_versions]
    rolling = [item for item in versions if item["version"] not in pinned_versions]
    rolling = rolling[: max_versions - len(pinned)]
    versions = sorted(
        [*pinned, *rolling],
        key=lambda item: version_key(item["version"]),
        reverse=True,
    )
    if (
        existing is not None
        and existing.get("max_versions") == max_versions
        and existing.get("latest") == versions[0]["version"]
        and existing.get("versions") == versions
    ):
        # A no-change scheduled run must not rotate generated_at and create a
        # needless manifest/checksum cache-coherency window at the CDN edge.
        return existing
    manifest = {
        "schema_version": 1,
        "product": "chrome-for-testing",
        "channel": "stable",
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": {"name": "Google Chrome for Testing", "manifest_url": SOURCE_MANIFEST_URL},
        "max_versions": max_versions,
        "latest": versions[0]["version"],
        "versions": versions,
    }
    validate_manifest(manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-entry", required=True)
    parser.add_argument("--existing-manifest")
    parser.add_argument("--max-versions", type=int, required=True)
    parser.add_argument("--pinned-versions-file")
    parser.add_argument("--output", required=True)
    parser.add_argument("--checksum-output", required=True)
    args = parser.parse_args()

    entry = load_json(args.release_entry)
    existing = None
    if args.existing_manifest and Path(args.existing_manifest).is_file():
        existing = load_json(args.existing_manifest)
        validate_manifest(existing)
    pinned_versions = (
        load_pinned_versions(args.pinned_versions_file) if args.pinned_versions_file else []
    )
    manifest = build_manifest(entry, existing, args.max_versions, pinned_versions)
    write_json(args.output, manifest)
    from mirrorlib import sha256_file

    digest = sha256_file(args.output)
    Path(args.checksum_output).write_text(f"{digest}  manifest.json\n", encoding="utf-8")


if __name__ == "__main__":
    main()
