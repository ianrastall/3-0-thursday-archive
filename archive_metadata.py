#!/usr/bin/env python3
"""Build 3-0 Thursday metadata and optionally import selected PGNs.

3-0 Thursday is a weekly Chess.com prize event for titled players that began on
November 13, 2025. Three tournaments run every Thursday (11 a.m., 4 p.m., and
9 p.m. ET), captured here as sessions ``a``, ``b``, and ``c`` (First / Second /
Third). Filenames follow ``3-0-thursday_YYYY-MM-DD[a|b|c].(zip|pgn)``; each ZIP
holds one identically named PGN whose game content is never modified.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import re
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENT = '3-0 Thursday'
BASE_URL = 'https://github.com/ianrastall/3-0-thursday-archive/raw/main'

SESSION_LETTER = {'first': 'a', 'second': 'b', 'third': 'c'}
LETTER_SESSION = {'a': 'First', 'b': 'Second', 'c': 'Third'}

# Canonical, already-standardized name: 3-0-thursday_2026-01-01a.pgn
CANONICAL_NAME = re.compile(
    r'^3-0-thursday_(\d{4})-(\d{2})-(\d{2})([abc])\.(?:pgn|zip)$', re.I
)
# Legacy export name: 2025-3-0-thursday-november-13-first.pgn
LEGACY_NAME = re.compile(
    r'^(\d{4})-3-0-thursday-([a-z]+)-(\d{1,2})-(first|second|third)\.pgn$', re.I
)
HEADER = re.compile(rb'^\[([A-Za-z0-9_]+) "([^"\r\n]*)"\]\s*$', re.M)

_MONTHS = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}


def parse_name(filename: str) -> tuple[str, str]:
    """Return (iso_date, letter) for a recognized 3-0 Thursday filename."""
    match = CANONICAL_NAME.fullmatch(filename)
    if match:
        return date(int(match[1]), int(match[2]), int(match[3])).isoformat(), match[4].lower()
    match = LEGACY_NAME.fullmatch(filename)
    if match:
        iso = date(int(match[1]), _MONTHS[match[2].lower()], int(match[3])).isoformat()
        return iso, SESSION_LETTER[match[4].lower()]
    raise ValueError(f'Unrecognized 3-0 Thursday filename: {filename}')


def canonical_stem(iso_date: str, letter: str) -> str:
    return f'3-0-thursday_{iso_date}{letter}'


def pgn_metadata(content: bytes) -> tuple[str, int]:
    tags: dict[bytes, list[bytes]] = {}
    for name, value in HEADER.findall(content.removeprefix(b'\xef\xbb\xbf')):
        tags.setdefault(name, []).append(value)
    events = tags.get(b'Event', [])
    if not events:
        raise ValueError('PGN has no Event headers.')
    for name in (b'White', b'Black', b'Result'):
        if len(tags.get(name, [])) != len(events):
            raise ValueError(f'PGN has missing or duplicate {name.decode()} headers.')
    return events[0].decode('utf-8').strip(), len(events)


def entry_metadata(filename: str, pgn: str, letter: str, source_event: str,
                   games: int, sha256: str) -> dict:
    iso_date, _ = parse_name(filename)
    year = int(iso_date[:4])
    return {
        'pgn': pgn,
        'zip': filename,
        'year': year,
        'date': iso_date,
        'session': LETTER_SESSION[letter],
        'event': EVENT,
        'sourceEvent': source_event,
        'games': games,
        'url': f'{BASE_URL}/{year}/{filename}',
        'sha256': sha256,
    }


def read_zip(path: Path) -> dict:
    iso_date, letter = parse_name(path.name)
    if path.parent.name != iso_date[:4]:
        raise ValueError(f'Wrong year folder: {path}')
    expected = path.with_suffix('.pgn').name
    with zipfile.ZipFile(path) as archive:
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        if names != [expected]:
            raise ValueError(f'Expected one canonical PGN in {path}: {names}')
        source_event, games = pgn_metadata(archive.read(expected))
    return entry_metadata(path.name, expected, letter, source_event, games,
                          hashlib.sha256(path.read_bytes()).hexdigest())


def render_metadata(entries: list[dict]) -> dict[str, str]:
    entries = sorted(entries, key=lambda entry: entry['zip'])
    return {
        't30_manifest.json': json.dumps(entries, ensure_ascii=False, indent=2) + '\n',
        't30_links.txt': ''.join(f"{entry['url']}\n" for entry in entries),
        't30_events.txt': ''.join(f"{entry['pgn']}: {entry['sourceEvent']}\n" for entry in entries),
        't30_game_counts.txt': ''.join(f"{entry['pgn']}: {entry['games']}\n" for entry in entries),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import-pgn', type=Path, nargs='+', default=[],
                        help='Selected PGNs; their filenames determine event dates and sessions.')
    parser.add_argument('--write', action='store_true',
                        help='Create new ZIPs and write metadata. Otherwise preview only.')
    args = parser.parse_args()

    entries = [read_zip(path) for path in sorted(ROOT.glob('20[0-9][0-9]/*.zip'))]
    known = {entry['zip'] for entry in entries}
    pending = []
    for source in args.import_pgn:
        iso_date, letter = parse_name(source.name)
        filename = canonical_stem(iso_date, letter) + '.zip'
        if filename in known:
            raise ValueError(f'Archive already exists or was selected twice: {filename}')
        content = source.read_bytes()
        source_event, games = pgn_metadata(content)
        known.add(filename)
        pending.append((source, filename, letter, source_event, games,
                        hashlib.sha256(content).hexdigest()))
        print(f'{source.name} -> {filename}: {games:,} games', flush=True)

    if not args.write:
        print(f'Validated {len(entries)} existing ZIPs and {len(pending)} new PGNs. Add --write to save.')
        return

    for source, filename, letter, source_event, games, digest in pending:
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f'Source changed during import: {source}')
        iso_date, _ = parse_name(filename)
        destination = ROOT / iso_date[:4] / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix('.zip.tmp')
        pgn = filename.removesuffix('.zip') + '.pgn'
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr(pgn, content)
        with zipfile.ZipFile(temporary) as archive:
            if archive.namelist() != [pgn] or archive.read(pgn) != content:
                raise ValueError(f'ZIP verification failed: {destination}')
        temporary.rename(destination)
        entries.append(entry_metadata(filename, pgn, letter, source_event, games,
                                      hashlib.sha256(destination.read_bytes()).hexdigest()))

    for name, content in render_metadata(entries).items():
        target = ROOT / name
        if target.exists() and target.read_text(encoding='utf-8-sig') == content:
            continue
        temporary = target.with_suffix(target.suffix + '.tmp')
        temporary.write_text(content, encoding='utf-8', newline='\n')
        temporary.replace(target)
    print(f'Wrote {len(entries)} events and {sum(entry["games"] for entry in entries):,} games.')


if __name__ == '__main__':
    main()
