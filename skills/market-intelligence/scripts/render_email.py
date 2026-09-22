#!/usr/bin/env python3
"""
render_email.py - newsletter renderer of the market-intelligence skill.

Turns the brief, written by the model as a small JSON file, into a
friendly HTML newsletter plus a plain-text fallback, so the model never
writes HTML and the layout is identical on every run. Sending is NOT done
here: the model passes the printed subject/html/text to the Resend MCP
`send-email` tool.

Subcommands
  render  --input brief.json [--date YYYY-MM-DD] [--no-save]
          Prints one JSON: {subject, html, text, html_path, email}.
          `email` is {to, from} from the config, or null when unconfigured.
  send    --input brief.json [--date YYYY-MM-DD]
          Renders, then sends through the Resend REST API. This is the FALLBACK
          for when the Resend MCP tool is not connected: the HTML never passes
          through the model. Prints {"sent": true, "id": ...}. Exit codes:
          0 sent, 1 bad input or unconfigured recipient, 3 no API key, 4 API error.
  config  [--to ADDRESS] [--from SENDER] [--api-key KEY]
          Sets (or, with no flag, prints) the email defaults. The key is stored
          in config.json (chmod 600) and always printed masked.

Brief JSON
  {
    "run_id": "20260919T...Z-ab12cd",          # names the saved HTML file
    "subject": "agentic commerce",             # human label of the watch
    "lang": "en",                              # en | fr | de | es (labels only)
    "window_days": 1,
    "note": "optional italic line",            # widened window, substitution...
    "articles": [                              # 1 to 5 items
      {"title": "...", "source": "Outlet",
       "summary": "Two or three short sentences.",
       "url": "https://publisher/...",
       "from_excerpt": false}
    ]
  }

State lives in $MI_STATE_DIR (default ~/.market-intelligence):
  config.json        email defaults {"email": {"to": ..., "from": ...}, "resend_api_key": ...}
  briefs/<run>.html  the rendered newsletter, to open in a browser

API key lookup for `send`: $RESEND_API_KEY first, then RESEND_API_KEY=... in
$MI_STATE_DIR/.env (one KEY=VALUE per line, '#' comments allowed, an optional
'export ' prefix is stripped), then "resend_api_key" in config.json. The .env
file lets a cron job keep the key out of the crontab; `chmod 600` it yourself.
$RESEND_API_URL overrides the endpoint (tests only).

Standard library only. Python >= 3.9.
"""

import argparse
import html as _html
import json
import os
import ssl
import stat
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


# --------------------------------------------------------------------------- #
# Labels (the brief is written in the language of the request)
# --------------------------------------------------------------------------- #

LABELS = {
    "en": {
        "kicker": "Market intelligence", "top_one": "Top 5 articles of the day",
        "top_n": "Top 5 articles of the last {n} days", "source": "Source",
        "read": "Read the article",
        "excerpt": "summary from excerpt", "subject_line": "{s} — your brief of {d}",
        "footer": "Sent by your market-intelligence skill. Summaries are generated from the linked articles.",
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "months": ["January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December"],
        "date": "{wd}, {m} {d}, {y}",
    },
    "fr": {
        "kicker": "Veille marché", "top_one": "Top 5 des articles du jour",
        "top_n": "Top 5 des articles des {n} derniers jours", "source": "Source",
        "read": "Lire l'article",
        "excerpt": "résumé à partir d'un extrait", "subject_line": "{s} — votre veille du {d}",
        "footer": "Envoyé par votre skill market-intelligence. Les résumés sont générés à partir des articles liés.",
        "days": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "months": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                   "septembre", "octobre", "novembre", "décembre"],
        "date": "{wd} {d} {m} {y}",
    },
    "de": {
        "kicker": "Marktbeobachtung", "top_one": "Top 5 Artikel des Tages",
        "top_n": "Top 5 Artikel der letzten {n} Tage", "source": "Quelle",
        "read": "Artikel lesen",
        "excerpt": "Zusammenfassung aus einem Auszug", "subject_line": "{s} — Ihr Überblick vom {d}",
        "footer": "Gesendet von Ihrem market-intelligence-Skill. Die Zusammenfassungen stammen aus den verlinkten Artikeln.",
        "days": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
        "months": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
                   "September", "Oktober", "November", "Dezember"],
        "date": "{wd}, {d}. {m} {y}",
    },
    "es": {
        "kicker": "Vigilancia de mercado", "top_one": "Top 5 artículos del día",
        "top_n": "Top 5 artículos de los últimos {n} días", "source": "Fuente",
        "read": "Leer el artículo",
        "excerpt": "resumen a partir de un extracto", "subject_line": "{s} — tu resumen del {d}",
        "footer": "Enviado por tu skill market-intelligence. Los resúmenes se generan a partir de los artículos enlazados.",
        "days": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
        "months": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                   "septiembre", "octubre", "noviembre", "diciembre"],
        "date": "{wd}, {d} de {m} de {y}",
    },
}

# Palette: warm paper background, ink text, burnt-orange accent. Dark-mode
# overrides live in the <style> block (clients that ignore it keep the light look).
BG, CARD, INK, MUTED, LINE, ACCENT, ACCENT_BG = "#f5f1ea", "#ffffff", "#1f2933", "#66707a", "#e6dfd3", "#c2410c", "#fdeee4"
SERIF = "Georgia,'Times New Roman',serif"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


def f(size: int, lh: int, weight: int = 400, serif: bool = False, extra: str = "") -> str:
    """Compact font declarations. The sans family is set once on <body> and the wrapper
    table and inherited; only serif text repeats its family (keeps the HTML small)."""
    fam = f"font-family:{SERIF};" if serif else ""
    w = f"font-weight:{weight};" if weight != 400 else ""
    return f"{fam}font-size:{size}px;line-height:{lh}px;{w}{extra}".rstrip(";")

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def state_dir() -> Path:
    d = Path(os.environ.get("MI_STATE_DIR", "~/.market-intelligence")).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def esc(text) -> str:
    return _html.escape(str(text), quote=True)


def clean_url(url: str) -> str:
    """Only plain publisher http(s) links; never a Google News redirect."""
    p = urlparse((url or "").strip())
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError(f"not a usable http(s) url: {url!r}")
    if p.netloc.lower().endswith("news.google.com"):
        raise ValueError(f"news.google.com link is not a publisher url: {url!r}")
    return p.geturl()


def validate(brief: dict) -> dict:
    """Return a normalized copy of the brief or raise ValueError with a precise message."""
    if not str(brief.get("subject", "")).strip():
        raise ValueError("missing 'subject'")
    arts = brief.get("articles")
    if not isinstance(arts, list) or not 1 <= len(arts) <= 5:
        raise ValueError("'articles' must hold 1 to 5 items")
    out = {"subject": str(brief["subject"]).strip(), "lang": brief.get("lang", "en"),
           "window_days": int(brief.get("window_days", 1) or 1), "note": str(brief.get("note", "") or "").strip(),
           "run_id": str(brief.get("run_id", "") or ""), "articles": []}
    if out["lang"] not in LABELS:
        out["lang"] = "en"
    for i, a in enumerate(arts, 1):
        summary = " ".join(str(a.get("summary", "")).split())
        if not str(a.get("title", "")).strip() or not summary:
            raise ValueError(f"article {i}: needs 'title' and 'summary'")
        if ";" in summary:
            raise ValueError(f"article {i}: no semicolons in 'summary', use two sentences or a comma")
        out["articles"].append({
            "title": str(a["title"]).strip(), "source": str(a.get("source", "")).strip(),
            "summary": summary, "url": clean_url(a.get("url", "")),
            "from_excerpt": bool(a.get("from_excerpt", False))})
    return out


def fmt_date(d: datetime, lab: dict) -> str:
    return lab["date"].format(wd=lab["days"][d.weekday()], m=lab["months"][d.month - 1], d=d.day, y=d.year)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def heading(brief: dict, lab: dict) -> str:
    n = brief["window_days"]
    return lab["top_one"] if n == 1 else lab["top_n"].format(n=n)


def render_html(brief: dict, lab: dict, date_str: str) -> str:
    def card(i: int, a: dict) -> str:
        src = f"<b>{esc(a['source'])}</b>" if a["source"] else ""
        excerpt = (f'<p class="mu" style="margin:0 0 12px;{f(13, 18, extra="font-style:italic;")};color:{MUTED}">'
                   f'({esc(lab["excerpt"])})</p>' if a["from_excerpt"] else "")
        return f"""
<tr><td style="padding:0 0 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="card" style="background:{CARD};border:1px solid {LINE};border-radius:14px"><tr><td class="pad" style="padding:30px 36px">
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 12px"><tr>
<td class="abg ac" style="width:28px;height:28px;background:{ACCENT_BG};color:{ACCENT};border-radius:14px;text-align:center;{f(14, 28, weight=700)}">{i}</td>
<td class="mu" style="padding-left:10px;{f(13, 18)};color:{MUTED}">{src}</td></tr></table>
<h2 class="ink" style="margin:0 0 12px;{f(25, 33, weight=700, serif=True)};color:{INK}">{esc(a['title'])}</h2>
<p class="ink" style="margin:0 0 18px;{f(16, 26)};color:{INK}">{esc(a['summary'])}</p>{excerpt}
<a href="{esc(a['url'])}" style="display:inline-block;margin-top:6px;padding:12px 24px;background:{ACCENT};color:#ffffff;text-decoration:none;border-radius:999px;{f(14, 20, weight=600)}">{esc(lab['read'])} →</a>
</td></tr></table></td></tr>"""

    cards = "".join(card(i, a) for i, a in enumerate(brief["articles"], 1))
    note = (f'<tr><td class="mu" style="padding:8px 4px 0;{f(13, 19, extra="font-style:italic;")};color:{MUTED}">{esc(brief["note"])}</td></tr>'
            if brief["note"] else "")
    preheader = esc(brief["articles"][0]["title"])
    return f"""<!DOCTYPE html>
<html lang="{esc(brief['lang'])}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<title>{esc(brief['subject'])}</title>
<style>
@media (prefers-color-scheme:dark){{
body,.bg{{background:#15181c!important}}
.card{{background:#1f242a!important;border-color:#333a42!important}}
.ink,.ink a{{color:#eceff2!important}}
.mu{{color:#9aa4ae!important}}
.abg{{background:#3a2418!important}}
.ac{{color:#fb923c!important}}
}}
@media (max-width:740px){{.wrap{{width:100%!important}}.pad{{padding:24px 20px!important}}}}
</style></head>
<body class="bg" style="margin:0;padding:0;background:{BG};font-family:{SANS}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="bg" style="background:{BG}"><tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="720" cellpadding="0" cellspacing="0" class="wrap" style="width:720px;max-width:100%;font-family:{SANS}">
<tr><td style="padding:0 4px 22px">
<p class="ac" style="margin:0 0 6px;{f(12, 16, weight=700)};letter-spacing:2px;text-transform:uppercase;color:{ACCENT}">{esc(lab['kicker'])}</p>
<h1 class="ink" style="margin:0 0 6px;{f(32, 38, weight=700, serif=True)};color:{INK}">{esc(brief['subject'][:1].upper() + brief['subject'][1:])}</h1>
<p class="mu" style="margin:0;{f(14, 20)};color:{MUTED}">{esc(date_str)}</p></td></tr>
<tr><td style="padding:0 4px 14px"><h2 class="ink" style="margin:0;{f(13, 18, weight=700)};letter-spacing:1px;text-transform:uppercase;color:{INK}">{esc(heading(brief, lab))}</h2></td></tr>
{cards}{note}
<tr><td class="mu" style="padding:24px 4px 0;border-top:1px solid {LINE};{f(12, 18)};color:{MUTED}">{esc(lab['footer'])}</td></tr>
</table></td></tr></table></body></html>"""


def render_text(brief: dict, lab: dict, date_str: str) -> str:
    lines = [f"{brief['subject']} — {date_str}", "", heading(brief, lab).upper(), ""]
    for i, a in enumerate(brief["articles"], 1):
        lines += [f"{i}. {a['title']}", f"{lab['source']}: {a['source']}", a["summary"]]
        if a["from_excerpt"]:
            lines.append(f"({lab['excerpt']})")
        lines += [a["url"], ""]
    if brief["note"]:
        lines += [brief["note"], ""]
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Subcommands
# --------------------------------------------------------------------------- #


def read_config() -> dict:
    p = state_dir() / "config.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


def build_email(args) -> dict:
    """Validate and render. Raises ValueError/OSError with a message fit for the JSON `error` field."""
    try:
        raw = json.loads(sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8"))
        brief = validate(raw)
        date = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.now()
    except (TypeError, AttributeError) as e:
        raise ValueError(f"malformed brief: {e}") from e
    lab = LABELS[brief["lang"]]
    date_str = fmt_date(date, lab)
    html_doc = render_html(brief, lab, date_str)
    html_path = ""
    if not getattr(args, "no_save", False):
        name = brief["run_id"] or date.strftime("%Y%m%d") + "-brief"
        p = state_dir() / "briefs" / f"{name}.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html_doc, encoding="utf-8")
        html_path = str(p)
    em = read_config().get("email") or {}
    return {"subject": lab["subject_line"].format(s=brief["subject"][:1].upper() + brief["subject"][1:], d=date_str),
            "html_path": html_path,
            "email": {"to": em["to"], "from": em["from"]} if em.get("to") and em.get("from") else None,
            "text": render_text(brief, lab, date_str), "html": html_doc}


def run_render(args) -> int:
    try:
        out = build_email(args)
    except (OSError, ValueError) as e:  # JSONDecodeError is a ValueError
        print(json.dumps({"error": str(e)}))
        return 1
    print(json.dumps(out, ensure_ascii=False))
    return 0


def load_dotenv() -> None:
    """Load KEY=VALUE lines from $MI_STATE_DIR/.env into the environment, without
    overriding a variable already set (e.g. exported by the crontab itself)."""
    p = state_dir() / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def api_key() -> str:
    load_dotenv()
    return (os.environ.get("RESEND_API_KEY") or read_config().get("resend_api_key") or "").strip()


def tls_context() -> ssl.SSLContext:
    """Verified TLS. python.org builds on macOS ship without a CA bundle, so prefer certifi
    (a dependency of `requests`, which fetch_news.py already needs) when it is installed."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def run_send(args) -> int:
    """Fallback path: POST the rendered email to the Resend REST API."""
    try:
        out = build_email(args)
    except (OSError, ValueError) as e:
        print(json.dumps({"error": str(e)}))
        return 1
    if not out["email"]:
        print(json.dumps({"error": "no recipient configured: run `render_email.py config --to ... --from ...`"}))
        return 1
    key = api_key()
    if not key:
        print(json.dumps({"error": "no Resend API key: set $RESEND_API_KEY or run `render_email.py config --api-key ...`"}))
        return 3
    payload = {"from": out["email"]["from"], "to": [out["email"]["to"]], "subject": out["subject"],
               "html": out["html"], "text": out["text"]}
    req = urllib.request.Request(
        os.environ.get("RESEND_API_URL", "https://api.resend.com/emails"),
        data=json.dumps(payload).encode("utf-8"), method="POST",
        # Resend sits behind Cloudflare, which rejects the default Python user agent.
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "market-intelligence-skill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=tls_context()) as resp:
            body = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8")).get("message", "")
        except (ValueError, AttributeError):
            detail = ""
        print(json.dumps({"error": f"resend api {e.code}: {detail or e.reason}", "html_path": out["html_path"]}))
        return 4
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(json.dumps({"error": f"resend api unreachable: {e}", "html_path": out["html_path"]}))
        return 4
    print(json.dumps({"sent": True, "id": body.get("id", ""), "to": out["email"]["to"], "subject": out["subject"],
                      "html_path": out["html_path"]}, ensure_ascii=False))
    return 0


def masked(cfg: dict) -> dict:
    shown = dict(cfg)
    if shown.get("resend_api_key"):
        shown["resend_api_key"] = "…" + shown["resend_api_key"][-4:]
    return shown


def run_config(args) -> int:
    cfg = read_config()
    if args.to or args.sender or args.api_key:
        if args.to or args.sender:
            em = cfg.setdefault("email", {})
            if args.to:
                em["to"] = args.to
            if args.sender:
                em["from"] = args.sender
        if args.api_key:
            cfg["resend_api_key"] = args.api_key.strip()
        p = state_dir() / "config.json"
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        p.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(json.dumps(masked(cfg), indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="render the brief JSON to newsletter HTML + text")
    r.add_argument("--input", required=True, help="brief JSON file, or - for stdin")
    r.add_argument("--date", help="YYYY-MM-DD shown in the header (default today)")
    r.add_argument("--no-save", action="store_true", help="do not write briefs/<run>.html")
    r.set_defaults(func=run_render)
    sd = sub.add_parser("send", help="render and send through the Resend REST API (MCP fallback)")
    sd.add_argument("--input", required=True, help="brief JSON file, or - for stdin")
    sd.add_argument("--date", help="YYYY-MM-DD shown in the header (default today)")
    sd.set_defaults(func=run_send)
    c = sub.add_parser("config", help="set or show the email defaults")
    c.add_argument("--to")
    c.add_argument("--from", dest="sender")
    c.add_argument("--api-key", dest="api_key", help="Resend API key for `send` (stored chmod 600, printed masked)")
    c.set_defaults(func=run_config)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
