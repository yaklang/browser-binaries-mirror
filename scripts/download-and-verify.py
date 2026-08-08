#!/usr/bin/env python3
"""Download, ZIP-test, hash, and describe all release artifacts."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import subprocess
from pathlib import Path

from mirrorlib import load_json, sha256_file, validate_zip_layout, write_json


def download_one(artifact: dict, output_dir: Path) -> dict:
    target = output_dir / artifact["filename"]
    subprocess.run(
        [
            "curl",
            "--silent",
            "--show-error",
            "--fail",
            "--location",
            "--retry",
            "5",
            "--retry-all-errors",
            "--continue-at",
            "-",
            "--output",
            str(target),
            artifact["source_url"],
        ],
        check=True,
    )
    subprocess.run(["unzip", "-tq", str(target)], check=True)
    validate_zip_layout(target, artifact)
    digest = sha256_file(target)
    checksum_path = output_dir / f"{artifact['filename']}.sha256.txt"
    checksum_path.write_text(f"{digest}  {artifact['filename']}\n", encoding="utf-8")
    return {**artifact, "sha256": digest, "size": target.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--entry-output", required=True)
    args = parser.parse_args()

    release = load_json(args.release)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        artifacts = list(pool.map(lambda item: download_one(item, output_dir), release["artifacts"]))
    artifacts.sort(key=lambda item: (item["os"], item["arch"]))
    write_json(
        args.entry_output,
        {
            "version": release["version"],
            "revision": release["revision"],
            "channel": "stable",
            "mirrored_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "artifacts": artifacts,
        },
    )


if __name__ == "__main__":
    main()
