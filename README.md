# 3-0-thursday-archive

Chess.com **3-0 Thursday** games, renamed and organized for the Chess Nerd
archive. 3-0 Thursday is a weekly prize event for titled players that debuted on
**November 13, 2025**. Three tournaments run every Thursday — 11 a.m., 4 p.m.,
and 9 p.m. ET — recorded here as sessions **First / Second / Third** (`a` / `b` /
`c`). The collection currently covers November 13, 2025 through October 8, 2026.

## Data and naming

ZIPs live in year folders. Each ZIP contains one matching PGN, for example:

`2026/3-0-thursday_2026-01-01a.zip` → `3-0-thursday_2026-01-01a.pgn`

Filenames follow `3-0-thursday_YYYY-MM-DD[a|b|c].(zip|pgn)`: the ISO date of the
Thursday plus the session letter. PGN game content is never modified — only the
file is renamed and zipped.

`t30_manifest.json` is the structured source for the Chess Nerd archive page.
`t30_links.txt`, `t30_events.txt`, and `t30_game_counts.txt` are generated
compatibility exports.

## Importing new events

Drop the raw session PGNs anywhere and run:

```
python archive_metadata.py --import-pgn path/to/*.pgn --write
```

The importer recognizes both the canonical `3-0-thursday_YYYY-MM-DD[a|b|c].pgn`
names and the legacy `YYYY-3-0-thursday-<month>-DD-<first|second|third>.pgn`
export names, packs each into a verified ZIP under the right year folder, and
regenerates the manifest and sidecar exports. Run it with no arguments to
validate every existing ZIP.
