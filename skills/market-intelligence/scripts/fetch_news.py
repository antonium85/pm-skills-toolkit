#!/usr/bin/env python3
"""
fetch_news.py - deterministic front-end of the market-intelligence skill.

Fetches Google News RSS for a subject, filters/dedupes/scores the items,
excludes articles already seen (cross-run ledger), resolves Google redirect
links to publisher URLs, and prints a compact JSON payload for the model.

Subcommands
  fetch   --subject "..." [--query '"phrase" OR term -excluded'] [--days N | --since YYYY-MM-DD]
          [--lang en-US] [--limit 10] [--no-widen] [--no-resolve] [--pretty]
          --subject is the human label (scoring, ledger); --query is the Google News
          search string when it differs (quotes, OR, -exclusions supported).
  mark    --run RUN_ID --shown KEY[,KEY...]      record shown/surfaced articles
  reject  KEY [KEY ...] [--reason "..."]          never show these again
  forget  KEY [KEY ...]                           drop keys from the ledger
  stats                                           ledger summary

State lives in $MI_STATE_DIR (default ~/.market-intelligence):
  seen.jsonl        append-only ledger, latest record per key wins
  runs/<run>.json   candidates of each run (needed by `mark`)

Only dependency: `requests` (stdlib otherwise). Python >= 3.9.
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

try:
    import requests
except ImportError:  # pragma: no cover
    sys.stderr.write("fetch_news.py needs the 'requests' package: pip install requests\n")
    sys.exit(2)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
GN_RSS = "https://news.google.com/rss/search"
GN_BATCH = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
# Bypasses the EU consent interstitial on news.google.com (no login involved).
GN_COOKIES = {"CONSENT": "PENDING+987", "SOCS": "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmVuIAEaBgiA_LyaBg"}

TIMEOUT = 12
WIDEN_LADDER = [1, 3, 7, 14]
LEDGER_TTL_DAYS = 90
MIN_STRONG = 3               # widen when fewer than this many candidates match the subject well
STRONG_MATCH = 0.6
SIM_THRESHOLD = 0.6          # title token Jaccard above which two items are "the same story"
MIN_TOKENS_FOR_SIM = 4
TIER_WEIGHT = {1: 1.0, 2: 0.75, 0: 0.5, 3: 0.2}   # 0 = unknown source
W_RECENCY, W_TIER, W_MATCH = 0.25, 0.25, 0.50

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
                   "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "cmpid", "s", "sh"}

STOPWORDS = set("""
a an the and or of to in on for with by from at as is are was be its it this that these those into over
after before about vs via how why what when where who new says said will can could may
le la les un une des du de et ou en au aux pour par sur dans avec est sont ce cette ces son sa ses
""".split())

LANG_PRESETS = {
    "en-US": ("en-US", "US", "US:en"),
    "en-GB": ("en-GB", "GB", "GB:en"),
    "fr-FR": ("fr", "FR", "FR:fr"),
    "de-DE": ("de", "DE", "DE:de"),
    "es-ES": ("es", "ES", "ES:es"),
}

DEFAULT_SOURCES = {
    "tiers": {
        "1": ["reuters.com", "bloomberg.com", "ft.com", "wsj.com", "nytimes.com", "economist.com",
              "theverge.com", "techcrunch.com", "wired.com", "arstechnica.com", "theinformation.com",
              "lesechos.fr", "lemonde.fr", "hbr.org", "mckinsey.com", "stratechery.com"],
        "2": ["cnbc.com", "forbes.com", "businessinsider.com", "axios.com", "venturebeat.com",
              "zdnet.com", "pymnts.com", "digiday.com", "retaildive.com", "modernretail.co",
              "thefinancialbrand.com", "fastcompany.com", "engadget.com", "9to5google.com",
              "blog.google", "openai.com", "anthropic.com", "microsoft.com", "aws.amazon.com",
              "shopify.com", "stripe.com", "mastercard.com", "visa.com", "frenchweb.fr",
              "maddyness.com", "journaldunet.com", "usine-digitale.fr", "lsa-conso.fr"],
        "3": ["prnewswire.com", "businesswire.com", "globenewswire.com", "accesswire.com",
              "einpresswire.com", "openpr.com", "newswire.com", "prweb.com", "medium.com",
              "linkedin.com", "yahoo.com", "marketwatch.com", "benzinga.com", "fool.com"]
    },
    "blocklist": ["einpresswire.com", "openpr.com", "digitaljournal.com", "marketscreener.com",
                  "streetinsider.com", "globalbankingandfinance.com", "issuewire.com"],
    "paywall": ["wsj.com", "ft.com", "bloomberg.com", "economist.com", "theinformation.com",
                "stratechery.com", "lesechos.fr", "latribune.fr", "lopinion.fr"]
}

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def state_dir() -> Path:
    d = Path(os.environ.get("MI_STATE_DIR", "~/.market-intelligence")).expanduser()
    (d / "runs").mkdir(parents=True, exist_ok=True)
    return d


def load_sources() -> dict:
    """references/sources.json next to the skill, else built-in defaults."""
    cfg = Path(__file__).resolve().parent.parent / "references" / "sources.json"
    if cfg.exists():
        try:
            return json.loads(cfg.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.stderr.write(f"warning: {cfg} is not valid JSON ({e}); using defaults\n")
    return DEFAULT_SOURCES


def domain_of(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def tier_of(domain: str, sources: dict) -> int:
    for tier, domains in sources.get("tiers", {}).items():
        if any(domain == d or domain.endswith("." + d) for d in domains):
            return int(tier)
    return 0


def in_domain_list(domain: str, sources: dict, key: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in sources.get(key, []))


def is_blocked(domain: str, sources: dict) -> bool:
    return in_domain_list(domain, sources, "blocklist")


def is_paywalled(domain: str, sources: dict) -> bool:
    return in_domain_list(domain, sources, "paywall")


def normalize_url(url: str) -> str:
    p = urlparse(url)
    host = p.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False)
         if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")]
    path = re.sub(r"/amp/?$", "/", p.path) or "/"
    path = path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower() or "https", host, path, "", urlencode(sorted(q)), ""))


def norm_title(title: str) -> str:
    t = html.unescape(title or "")
    t = re.sub(r"\s+[-|–—]\s+[^-|–—]{2,60}$", "", t)   # strip trailing " - Source"
    t = t.lower()
    t = re.sub(r"\be[\s\-]?commerce\b", "ecommerce", t)   # e-commerce / e commerce / ecommerce
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


def tokens(text: str) -> set:
    """Meaningful words: stopwords out, single letters out, 2-letter acronyms (IA, AI, UX) kept."""
    return {w for w in norm_title(text).split() if w not in STOPWORDS and len(w) >= 2}


def token_hit(needle: str, haystack: set) -> bool:
    """Exact token match, or containment for longer words (commerce ~ ecommerce, agent ~ agents)."""
    if needle in haystack:
        return True
    if len(needle) >= 5:
        return any(len(w) >= 5 and (needle in w or w in needle) for w in haystack)
    return False


def match_ratio(subject_tokens: set, title_tokens: set) -> float:
    if not subject_tokens:
        return 0.5
    return sum(1 for t in subject_tokens if token_hit(t, title_tokens)) / len(subject_tokens)


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def short_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def article_key(title: str, domain: str) -> str:
    return short_hash(norm_title(title) + "|" + domain)


def http_get(url, **kw):
    kw.setdefault("timeout", TIMEOUT)
    kw.setdefault("headers", {"User-Agent": UA})
    last = None
    for attempt in range(2):
        try:
            r = requests.get(url, **kw)
            if r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            return r
        except (requests.RequestException, requests.HTTPError) as e:
            last = e
            time.sleep(1.0 * (attempt + 1))
    raise last

# --------------------------------------------------------------------------- #
# Ledger
# --------------------------------------------------------------------------- #

def ledger_path() -> Path:
    return state_dir() / "seen.jsonl"


def read_ledger() -> dict:
    """Returns {key: latest_record}. Malformed lines are skipped, never fatal."""
    recs = {}
    p = ledger_path()
    if not p.exists():
        return recs
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                recs[r["key"]] = r
            except (json.JSONDecodeError, KeyError):
                continue
    return recs


def append_ledger(records: list) -> None:
    with ledger_path().open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def prune_ledger(ttl_days: int = LEDGER_TTL_DAYS) -> int:
    """Compacts to one record per key and drops records older than ttl. Atomic rewrite."""
    recs = read_ledger()
    cutoff = (now_utc() - timedelta(days=ttl_days)).isoformat()
    keep = [r for r in recs.values()
            if r.get("status") != "forgotten" and r.get("ts", "") >= cutoff]
    p = ledger_path()
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in sorted(keep, key=lambda r: r.get("ts", "")):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, p)
    return len(recs) - len(keep)


def is_seen(item: dict, ledger: dict, seen_tokens: list) -> bool:
    if item["key"] in ledger:
        return True
    if item.get("gn_token") and item["gn_token"] in {r.get("gn_token") for r in ledger.values()}:
        return True
    toks = item["_tokens"]
    if len(toks) >= MIN_TOKENS_FOR_SIM:
        for st in seen_tokens:
            if len(st) >= MIN_TOKENS_FOR_SIM and jaccard(toks, st) >= SIM_THRESHOLD:
                return True
    return False

# --------------------------------------------------------------------------- #
# Google News
# --------------------------------------------------------------------------- #

def gn_query_url(query: str, days: int, lang: str) -> str:
    hl, gl, ceid = LANG_PRESETS.get(lang, LANG_PRESETS["en-US"])
    q = f"{query} when:{days}d"
    return f"{GN_RSS}?q={quote(q)}&hl={hl}&gl={gl}&ceid={ceid}"


def fetch_rss(query: str, days: int, lang: str) -> list:
    r = http_get(gn_query_url(query, days, lang))
    root = ET.fromstring(r.content)
    items = []
    for it in root.findall("./channel/item"):
        title = html.unescape(it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src = it.find("source")
        source_name = (src.text or "").strip() if src is not None else ""
        source_url = src.get("url", "") if src is not None else ""
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate") or "").astimezone(timezone.utc)
        except (TypeError, ValueError):
            pub = None
        if not title or not link or pub is None:
            continue
        dom = domain_of(source_url)
        tok = link.split("/articles/")[1].split("?")[0] if "/articles/" in link else ""
        # Google appends " - Source" to titles; keep the clean one.
        clean_title = re.sub(r"\s+-\s+" + re.escape(source_name) + r"$", "", title) if source_name else title
        items.append({
            "key": article_key(clean_title, dom),
            "title": clean_title,
            "source": source_name,
            "domain": dom,
            "published": pub.isoformat(timespec="minutes"),
            "_pub": pub,
            "gn_link": link,
            "gn_token": tok,
            "_tokens": tokens(clean_title),
        })
    return items


def resolve_gn_link(link: str) -> str:
    """Decodes a news.google.com/rss/articles/... link to the publisher URL.
    Undocumented endpoint; returns '' on any failure so callers can fall back."""
    try:
        page = http_get(link, cookies=GN_COOKIES)
        sig = re.search(r'data-n-a-sg="([^"]+)"', page.text)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page.text)
        if not (sig and ts):
            return ""
        tok = link.split("/articles/")[1].split("?")[0]
        inner = json.dumps(["garturlreq", [["en-US", "US", ["FINANCE_TOP_INDICES", "WEB_TEST_1_0_0"],
                            None, None, 1, 1, "US:en", None, 180, None, None, None, None, None, 0,
                            None, None, [1608992183, 723341000]], "en-US", "US", 1, [2, 3, 4, 8],
                            1, 0, "655000234", 0, 0, None, 0], tok, int(ts.group(1)), sig.group(1)])
        payload = json.dumps([[["Fbv4je", inner, None, "generic"]]])
        resp = requests.post(GN_BATCH, data={"f.req": payload}, cookies=GN_COOKIES, timeout=TIMEOUT,
                             headers={"User-Agent": UA,
                                      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        body = resp.text
        # Preferred: parse the JSON envelope; fallback: regex.
        try:
            outer = json.loads(body.split("\n", 1)[1]) if body.startswith(")]}'") else json.loads(body)
            for row in outer:
                if isinstance(row, list) and len(row) > 2 and isinstance(row[2], str) and "garturlres" in row[2]:
                    inner_res = json.loads(row[2])
                    if isinstance(inner_res, list) and len(inner_res) > 1 and str(inner_res[1]).startswith("http"):
                        return inner_res[1]
        except (json.JSONDecodeError, IndexError, TypeError):
            pass
        seg = body.split("garturlres", 1)[-1]
        m = re.search(r'https?://[^"\\\s\]]+', seg)
        return m.group(0) if m else ""
    except Exception:
        return ""

# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #

def dedupe_in_run(items: list) -> tuple:
    """Same story from several outlets -> keep the best (tier, then recency). Returns (kept, dropped)."""
    items = sorted(items, key=lambda x: (x["tier_rank"], -x["_pub"].timestamp(), x["title"]))
    kept, dropped = [], 0
    for it in items:
        dup = any(it["key"] == k["key"] or
                  (len(it["_tokens"]) >= MIN_TOKENS_FOR_SIM and jaccard(it["_tokens"], k["_tokens"]) >= SIM_THRESHOLD)
                  for k in kept)
        if dup:
            dropped += 1
        else:
            kept.append(it)
    return kept, dropped


def query_terms(query: str) -> str:
    """Positive search terms of a Google News query: drops OR, quotes and -excluded words."""
    q = re.sub(r"\s-\S+", " ", " " + query)          # -crypto
    q = re.sub(r"\bOR\b", " ", q)
    return q.replace('"', " ")


def score_items(items: list, subject: str, query: str, days: int) -> None:
    """Topic match dominates (0.5), then source tier and recency (0.25 each).
    Match = best of subject-token ratio and query-term ratio, so OR-synonyms in the
    query do not dilute a title that matches the subject itself."""
    subj_tokens = tokens(subject)
    query_tokens = tokens(query_terms(query))
    horizon = max(days, 1) * 86400.0
    now = now_utc()
    for it in items:
        age = max(0.0, (now - it["_pub"]).total_seconds())
        recency = max(0.0, 1.0 - age / horizon)
        match = max(match_ratio(subj_tokens, it["_tokens"]), match_ratio(query_tokens, it["_tokens"]))
        it["match"] = round(match, 2)
        it["score"] = round(W_RECENCY * recency + W_TIER * TIER_WEIGHT[it["tier"]] + W_MATCH * match, 4)


def run_fetch(args) -> int:
    sources = load_sources()
    pruned = prune_ledger()
    ledger = read_ledger()
    seen_tokens = [tokens(r.get("title", "")) for r in ledger.values()]

    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days_req = max(1, (now_utc() - since).days + 1)
        explicit = True
    else:
        days_req = args.days
        explicit = args.days_explicit
    widen_allowed = not (explicit or args.no_widen)
    query = (args.query or args.subject).strip()

    days = days_req
    widened = False
    stats = {}
    while True:
        try:
            raw = fetch_rss(query, days, args.lang)
        except Exception as e:
            print(json.dumps({"error": f"google news rss unreachable: {e}", "candidates": []}))
            return 2
        cutoff = now_utc() - timedelta(days=days)
        in_window = [it for it in raw if it["_pub"] >= cutoff]
        for it in in_window:
            it["tier"] = tier_of(it["domain"], sources)
            it["tier_rank"] = {1: 0, 2: 1, 0: 2, 3: 3}[it["tier"]]
        not_blocked = [it for it in in_window if not is_blocked(it["domain"], sources)]
        readable = [it for it in not_blocked if not is_paywalled(it["domain"], sources)]
        fresh = [it for it in readable if not is_seen(it, ledger, seen_tokens)]
        deduped, dropped = dedupe_in_run(fresh)
        score_items(deduped, args.subject, query, days)
        strong = sum(1 for it in deduped if it["match"] >= STRONG_MATCH)
        stats = {"fetched": len(raw), "in_window": len(in_window),
                 "excluded_blocklist": len(in_window) - len(not_blocked),
                 "excluded_paywall": len(not_blocked) - len(readable),
                 "excluded_seen": len(readable) - len(fresh), "deduped": dropped,
                 "strong_match": strong}
        enough = len(deduped) >= args.limit and strong >= MIN_STRONG
        if enough or not widen_allowed or days >= WIDEN_LADDER[-1] or widened:
            break
        # one step up the ladder, once
        days = next((d for d in WIDEN_LADDER if d > days), WIDEN_LADDER[-1])
        widened = True

    deduped.sort(key=lambda x: (-x["score"], -x["_pub"].timestamp(), x["title"]))
    top = deduped[:args.limit]

    for it in top:
        url = "" if args.no_resolve else resolve_gn_link(it["gn_link"])
        if not args.no_resolve:
            time.sleep(0.3)
        it["url"] = normalize_url(url) if url else ""
        it["needs_lookup"] = not bool(url)
        if url:
            it["url_hash"] = short_hash(it["url"])

    t = now_utc()
    run_id = t.strftime("%Y%m%dT%H%M%S") + f"{t.microsecond // 1000:03d}Z-" + short_hash(args.subject)[:6]
    out = {
        "run_id": run_id,
        "subject": args.subject,
        "query": query,
        "lang": args.lang,
        "window_days_requested": days_req,
        "window_days_used": days,
        "widened": widened,
        "ledger_pruned": pruned,
        **stats,
        "candidates": [{k: v for k, v in it.items() if not k.startswith("_") and k not in ("tier_rank", "gn_link")}
                       for it in top],
    }
    (state_dir() / "runs" / f"{run_id}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0

# --------------------------------------------------------------------------- #
# mark / reject / forget / stats
# --------------------------------------------------------------------------- #

def _record(key, status, subject="", run_id="", title="", domain="", url="", gn_token="", reason=""):
    return {"key": key, "status": status, "ts": now_utc().isoformat(timespec="seconds"),
            "subject": subject, "run_id": run_id, "title": title, "domain": domain,
            "url": url, "gn_token": gn_token, "reason": reason}


def run_mark(args) -> int:
    p = state_dir() / "runs" / f"{args.run}.json"
    if not p.exists():
        print(json.dumps({"error": f"unknown run {args.run}"}))
        return 1
    run = json.loads(p.read_text(encoding="utf-8"))
    shown = {k.strip() for k in (args.shown or "").split(",") if k.strip()}
    unknown = shown - {c["key"] for c in run["candidates"]}
    if unknown:
        print(json.dumps({"error": f"keys not in run {args.run}: {sorted(unknown)}"}))
        return 1
    recs = [_record(c["key"], "shown" if c["key"] in shown else "surfaced", run["subject"], run["run_id"],
                    c["title"], c["domain"], c.get("url", ""), c.get("gn_token", ""))
            for c in run["candidates"]]
    append_ledger(recs)
    print(json.dumps({"marked_shown": len(shown), "marked_surfaced": len(recs) - len(shown), "run_id": run["run_id"]}))
    return 0


def _find_in_runs(key: str) -> dict:
    runs = sorted((state_dir() / "runs").glob("*.json"), reverse=True)
    for p in runs[:50]:
        try:
            run = json.loads(p.read_text(encoding="utf-8"))
            for c in run["candidates"]:
                if c["key"] == key:
                    return {**c, "subject": run.get("subject", ""), "run_id": run.get("run_id", "")}
        except (json.JSONDecodeError, KeyError):
            continue
    return {}


def run_reject(args) -> int:
    recs = []
    for key in args.keys:
        c = _find_in_runs(key) or read_ledger().get(key, {})
        recs.append(_record(key, "rejected", c.get("subject", ""), c.get("run_id", ""), c.get("title", ""),
                            c.get("domain", ""), c.get("url", ""), c.get("gn_token", ""), args.reason or ""))
    append_ledger(recs)
    print(json.dumps({"rejected": [r["key"] for r in recs]}))
    return 0


def run_forget(args) -> int:
    append_ledger([_record(k, "forgotten") for k in args.keys])
    prune_ledger()
    print(json.dumps({"forgotten": list(args.keys)}))
    return 0


def run_stats(args) -> int:
    recs = read_ledger()
    by_status, by_subject = {}, {}
    for r in recs.values():
        by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1
        by_subject[r.get("subject", "")] = by_subject.get(r.get("subject", ""), 0) + 1
    print(json.dumps({"ledger": str(ledger_path()), "records": len(recs), "by_status": by_status,
                      "by_subject": by_subject, "ttl_days": LEDGER_TTL_DAYS}, ensure_ascii=False, indent=2))
    return 0

# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="fetch, filter, rank and resolve candidates")
    f.add_argument("--subject", required=True, help="human label, used for scoring and the ledger")
    f.add_argument("--query", default="", help="Google News search string if different from the subject "
                   "(supports \"quoted phrases\", OR, -exclusions)")
    g = f.add_mutually_exclusive_group()
    g.add_argument("--days", type=int, default=None, help="window in days (default 1)")
    g.add_argument("--since", help="YYYY-MM-DD, explicit start date")
    f.add_argument("--lang", default="en-US", choices=sorted(LANG_PRESETS))
    f.add_argument("--limit", type=int, default=10)
    f.add_argument("--no-widen", action="store_true", help="never widen the window automatically")
    f.add_argument("--no-resolve", action="store_true", help="skip Google link decoding (faster)")
    f.add_argument("--pretty", action="store_true")
    f.set_defaults(func=run_fetch)

    m = sub.add_parser("mark", help="record a run's articles as shown/surfaced")
    m.add_argument("--run", required=True)
    m.add_argument("--shown", default="", help="comma-separated keys of the articles in the brief")
    m.set_defaults(func=run_mark)

    r = sub.add_parser("reject", help="never show these keys again")
    r.add_argument("keys", nargs="+")
    r.add_argument("--reason", default="")
    r.set_defaults(func=run_reject)

    fo = sub.add_parser("forget", help="drop keys from the ledger")
    fo.add_argument("keys", nargs="+")
    fo.set_defaults(func=run_forget)

    s = sub.add_parser("stats", help="ledger summary")
    s.set_defaults(func=run_stats)

    args = ap.parse_args(argv)
    if args.cmd == "fetch":
        args.days_explicit = args.days is not None
        if args.days is None:
            args.days = 1
        if args.days < 1:
            ap.error("--days must be >= 1")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
