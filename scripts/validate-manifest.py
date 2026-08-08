#!/usr/bin/env python3
"""Validate a local manifest against JSON Schema and custom invariants."""

from __future__ import annotations

import argparse

from mirrorlib import load_json, load_schema_and_validate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--schema", default="schemas/manifest.schema.json")
    args = parser.parse_args()
    load_schema_and_validate(load_json(args.manifest), args.schema)


if __name__ == "__main__":
    main()
