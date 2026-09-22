#!/usr/bin/env python3
"""
Schema-aware validator: checks every article in _articles/ against the schema
it declares, BEFORE the site is built. This is where malformed content should
be caught -- the renderer should never have to defend against it.

Checks, generically, from the schema definition alone (no field names hardcoded):
  - every non-optional field is present and non-empty
  - a field's shape matches its actual YAML type (text/list/table/boolean)
  - a field declared with max_chars is not longer than that limit
  - exactly one field in the schema is marked as the teaser (schema-level check,
    run once per schema file, not per article)
  - published articles pin schema_version to the schema's version
  - schemas used by published articles are content-locked (immutability)

Immutability policy
-------------------
Once an article is published, neither the article nor the schema it used may
change in place. Format evolution = a new schema file (e.g. schema-foo-v2.yml).
Old articles stay pinned to the locked schema. See README "Published = immutable".

Usage:
  python scripts/validate_schema.py
  python scripts/validate_schema.py --update-locks   # refresh schema-locks.yml
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys
from datetime import datetime, timezone

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
LOCKS_PATH = ROOT / "_data" / "schema-locks.yml"
LEDGER_PATH = ROOT / "_data" / "zenodo-ledger.yml"

PLACEHOLDER_DOI_PREFIXES = (
    "10.5281/zenodo.000",
    "10.5281/zenodo.xxxx",
    "doi:pending",
    "pending",
)


def load_front_matter(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if not m:
        raise ValueError("no front matter block found")
    return yaml.safe_load(m.group(1)) or {}


def file_hash(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_placeholder_doi(doi) -> bool:
    if not doi:
        return True
    d = str(doi).strip().lower()
    return any(d.startswith(p) for p in PLACEHOLDER_DOI_PREFIXES) or d in ("", "none", "null")


def is_published(fm: dict, slug: str, ledger: dict) -> bool:
    """An article is published if explicitly marked, or has a real DOI, or is in the Zenodo ledger."""
    status = str(fm.get("status") or "").strip().lower()
    if status in ("published", "live"):
        return True
    if fm.get("doi") and not is_placeholder_doi(fm.get("doi")):
        return True
    entry = ledger.get(slug) or {}
    if entry.get("doi") and not is_placeholder_doi(entry.get("doi")):
        return True
    return False


def check_schema_file(schema: dict) -> list[str]:
    errors = []
    if "version" not in schema:
        errors.append(f"schema '{schema.get('name', '?')}' is missing a top-level 'version' field")
    teasers = [f for f in schema.get("fields", []) if f.get("teaser")]
    if len(teasers) != 1:
        errors.append(
            f"schema '{schema.get('name', '?')}' must have exactly one teaser field, found {len(teasers)}"
        )
    return errors


def check_value_shape(field: dict, value) -> str | None:
    shape = field["shape"]
    if shape == "text" and not isinstance(value, str):
        return f"'{field['key']}' is declared shape 'text' but the value is not a string"
    if shape == "list" and not isinstance(value, list):
        return f"'{field['key']}' is declared shape 'list' but the value is not a list"
    if shape == "table":
        if not isinstance(value, list) or not all(isinstance(r, dict) for r in value):
            return f"'{field['key']}' is declared shape 'table' but the value is not a list of rows"
        for row in value:
            missing = [c for c in field.get("columns", []) if c not in row]
            if missing:
                return f"'{field['key']}' has a row missing column(s): {', '.join(missing)}"
    if shape == "boolean" and not isinstance(value, bool):
        return f"'{field['key']}' is declared shape 'boolean' but the value is not true/false"
    return None


def check_article(path: pathlib.Path, schemas: dict, ledger: dict) -> list[str]:
    fm = load_front_matter(path)
    errors = []
    slug = path.stem
    schema_name = fm.get("schema")
    if not schema_name:
        return errors  # base-only article is valid

    schema = schemas.get(schema_name)
    if not schema:
        return [f"references unknown schema '{schema_name}'"]

    # Pin: published articles must declare schema_version matching the schema
    published = is_published(fm, slug, ledger)
    schema_ver = schema.get("version")
    article_ver = fm.get("schema_version")
    if published:
        if article_ver is None:
            errors.append(
                f"published article must set schema_version (expected {schema_ver!r} for '{schema_name}') "
                f"-- pins the format used at publication time"
            )
        elif schema_ver is not None and article_ver != schema_ver:
            errors.append(
                f"schema_version {article_ver!r} does not match schema '{schema_name}' version {schema_ver!r} "
                f"-- published articles must not silently move to a new schema version; "
                f"use a new schema file instead"
            )

    for field in schema.get("fields", []):
        key = field["key"]
        value = fm.get(key)
        empty = value is None or value == "" or value == []
        if empty:
            if not field.get("optional"):
                errors.append(f"required field '{key}' ({field['label']}) is missing or empty")
            continue
        shape_error = check_value_shape(field, value)
        if shape_error:
            errors.append(shape_error)
        max_chars = field.get("max_chars")
        if max_chars and isinstance(value, str) and len(value) > max_chars:
            errors.append(
                f"'{key}' ({field['label']}) is {len(value)} characters, over its {max_chars}-character limit "
                f"-- this field is the schema's teaser, so it must stay short enough to stand alone in a listing"
            )
    return errors


def load_locks() -> dict:
    if LOCKS_PATH.is_file():
        data = yaml.safe_load(LOCKS_PATH.read_text()) or {}
        return data if isinstance(data, dict) else {}
    return {}


def load_ledger() -> dict:
    if LEDGER_PATH.is_file():
        data = yaml.safe_load(LEDGER_PATH.read_text()) or {}
        return data if isinstance(data, dict) else {}
    return {}


def check_schema_locks(
    schema_paths: dict[str, pathlib.Path],
    schemas: dict,
    articles: list[pathlib.Path],
    ledger: dict,
    locks: dict,
    update_locks: bool,
) -> tuple[list[str], dict]:
    """
    Enforce schema content immutability for schemas used by published articles.
    Returns (errors, updated_locks).
    """
    errors = []
    # Which schemas are used by at least one published article?
    published_schemas: dict[str, list[str]] = {}
    for p in articles:
        fm = load_front_matter(p)
        if not is_published(fm, p.stem, ledger):
            continue
        name = fm.get("schema")
        if name:
            published_schemas.setdefault(name, []).append(p.name)

    new_locks = dict(locks)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for schema_name, article_names in sorted(published_schemas.items()):
        path = schema_paths.get(schema_name)
        if not path or not path.is_file():
            errors.append(f"published articles reference missing schema file '{schema_name}'")
            continue
        current_hash = file_hash(path)
        schema = schemas.get(schema_name) or {}
        lock = locks.get(schema_name)

        if lock is None:
            # First time we see published articles on this schema → lock it
            if update_locks:
                new_locks[schema_name] = {
                    "version": schema.get("version"),
                    "content_hash": current_hash,
                    "locked_at": now,
                    "locked_by": sorted(article_names),
                }
                print(f"LOCK   {schema_name}: new lock (hash={current_hash[:12]}…)")
            else:
                errors.append(
                    f"schema '{schema_name}' is used by published article(s) "
                    f"({', '.join(article_names)}) but has no entry in "
                    f"_data/schema-locks.yml — run: python scripts/validate_schema.py --update-locks"
                )
            continue

        locked_hash = lock.get("content_hash")
        if locked_hash and locked_hash != current_hash:
            errors.append(
                f"schema '{schema_name}' has changed since it was locked "
                f"(locked hash {str(locked_hash)[:12]}…, current {current_hash[:12]}…). "
                f"Published articles must not have their schema amended in place. "
                f"Create a new schema file (e.g. {schema_name}-v2) for format changes, "
                f"or restore the locked content. "
                f"Articles holding the lock: {', '.join(lock.get('locked_by') or article_names)}"
            )
        elif update_locks:
            # Refresh metadata only (hash unchanged)
            new_locks[schema_name] = {
                **lock,
                "version": schema.get("version"),
                "locked_by": sorted(set((lock.get("locked_by") or []) + article_names)),
            }

    return errors, new_locks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate articles against schemas")
    parser.add_argument(
        "--update-locks",
        action="store_true",
        help="Write/refresh _data/schema-locks.yml for schemas used by published articles",
    )
    args = parser.parse_args()

    schema_paths: dict[str, pathlib.Path] = {}
    schemas: dict = {}
    for p in sorted((ROOT / "_data").glob("schema-*.yml")):
        if p.name == "schema-locks.yml":
            continue
        s = yaml.safe_load(p.read_text()) or {}
        schemas[p.stem] = s
        schema_paths[p.stem] = p

    ledger = load_ledger()
    locks = load_locks()
    articles = sorted((ROOT / "_articles").glob("*.md"))

    total_errors = 0

    for schema in schemas.values():
        for e in check_schema_file(schema):
            print(f"SCHEMA ERROR  {e}")
            total_errors += 1

    lock_errors, new_locks = check_schema_locks(
        schema_paths, schemas, articles, ledger, locks, args.update_locks
    )
    for e in lock_errors:
        print(f"LOCK ERROR  {e}")
        total_errors += 1

    if args.update_locks:
        LOCKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Preserve header comment style
        body = yaml.dump(new_locks, default_flow_style=False, sort_keys=True, allow_unicode=True)
        LOCKS_PATH.write_text(
            "# Schema content locks — see scripts/validate_schema.py\n"
            "# Do not hand-edit hashes unless restoring a known-good state.\n"
            + body,
            encoding="utf-8",
        )
        print(f"Wrote {LOCKS_PATH.relative_to(ROOT)}")

    for p in articles:
        errors = check_article(p, schemas, ledger)
        for e in errors:
            print(f"ERROR  {p.name}: {e}")
            total_errors += 1

    print(
        f"\nChecked {len(articles)} article(s) against {len(schemas)} schema(s): "
        f"{total_errors} error(s)."
    )
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
