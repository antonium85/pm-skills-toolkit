# Seen-articles ledger (`seen.jsonl`)

Location: `$MI_STATE_DIR/seen.jsonl`, default `~/.market-intelligence/seen.jsonl`.
The ledger lives **outside the skill folder**: the installed folder may be a
per-session copy, read-only, or replaced on every update.

Each run's candidates are also kept in `$MI_STATE_DIR/runs/<run_id>.json`;
`mark` and `reject` read titles and URLs from there.

## Format

JSONL file, one record per line, **append-only**. The latest record for a key
wins. On every `fetch`, the file is compacted (one line per key) and records
older than 90 days are dropped, through an atomic rewrite.

```json
{"key": "b9f2634d7c7a", "status": "shown", "ts": "2026-09-17T20:27:00+00:00",
 "subject": "agentic commerce", "run_id": "20260917T202700123Z-853fe7",
 "title": "Payment giants battle the fear factor in agentic commerce",
 "domain": "americanbanker.com", "url": "https://americanbanker.com/...",
 "gn_token": "CBMi...", "reason": ""}
```

| `status` | Meaning | Excluded from next runs |
|---|---|---|
| `shown` | one of the 3 articles in the brief | yes |
| `surfaced` | in the 10 candidates, listed at the bottom of the brief | yes |
| `rejected` | explicitly rejected by the user | yes |
| `forgotten` | rejection or mark undone | no (removed at next compaction) |

## Article identity

- `key` = first 12 hex chars of SHA-1(`normalized title | domain`). The title
  is lowercased, stripped of punctuation and of the " - Source" suffix Google
  appends.
- `gn_token` = the article identifier in the Google News link; stable for a
  given article.
- `url` = normalized publisher URL (no `www.`, no tracking parameters, no
  trailing slash), known only when link decoding succeeded.

## Matching rules (in `fetch`)

A candidate counts as already seen when any of these holds:

1. its `key` is in the ledger;
2. its `gn_token` is in the ledger;
3. its title has a Jaccard index ≥ 0.6 (on meaningful words, minus fr/en
   stopwords, titles of at least 4 words) with the title of a ledger article.
   This is what catches the same announcement picked up by another outlet.

The ledger is **global**, not per subject: an article read under "agentic
commerce" is not shown again under "AI checkout". For a separate memory per
subject, run with a different `MI_STATE_DIR`.

## Commands

```bash
fetch_news.py mark --run <run_id> --shown k1,k2,k3   # 3 shown, the others surfaced
fetch_news.py reject k1 [k2 ...] [--reason "..."]
fetch_news.py forget k1 [k2 ...]
fetch_news.py stats
```
