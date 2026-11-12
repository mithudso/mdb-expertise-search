#!/usr/bin/env python3
"""Validate the structure and paths in the maintained static file index."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mdbx.safety import _directory, _read_bytes, directory_lock


def validate(entries):
    if not isinstance(entries, list) or not entries:
        raise ValueError('index must be a nonempty record list')
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'path', 'purpose', 'bytes'}:
            raise ValueError('invalid index record')
        path = entry['path']
        if not isinstance(path, str) or not path or path in seen:
            raise ValueError('invalid or duplicate index path')
        relative = Path(path)
        if relative.is_absolute() or any(part in {'.', '..'} for part in relative.parts):
            raise ValueError('index path must be a regular relative file')
        if not isinstance(entry['purpose'], str) or (entry['bytes'] is not None and (type(entry['bytes']) is not int or entry['bytes'] < 0)):
            raise ValueError('invalid index metadata')
        seen.add(path)
        if not (ROOT / relative).is_file() or (ROOT / relative).is_symlink():
            raise ValueError('index contains an unavailable regular file')


def main():
    import os
    parent = _directory(ROOT / 'docs')
    try:
        with directory_lock(parent, 'static-documentation-indexes'):
            validate(json.loads(_read_bytes(parent, 'high_signal_file_index.json')))
    except (ValueError, OSError, TypeError, KeyError):
        print('invalid documentation index; regenerate the static indexes', file=sys.stderr)
        return 1
    finally:
        os.close(parent)
    print('doc index ok')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
