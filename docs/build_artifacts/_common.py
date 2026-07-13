"""Shared scaffolding for the citeval innovation artifacts (W1-INNOVATION).

These artifacts are **offline, self-contained HTML pages** built from committed
calibration data (zero Opus cost, no API key). Each `build_*.py` in this directory
reads canonical files under `corpus/calibration/` (and the frozen debate transcript)
and *bakes* the numbers into a standalone `.html` under `docs/artifacts/`, so the
page opens with a plain `file://` and renders even with the repo offline.

This module holds the design system (palette from the dataviz reference instance),
the HTML shell + cross-link nav, and small tested helpers. It is **not** an artifact
itself — it only produces no output on its own.

Nothing here imports `citeval` or touches `src/` — pages must render from committed
data alone.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

# --- Repo geography --------------------------------------------------------------
# docs/build_artifacts/_common.py  ->  parents[2] == repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
CAL_DIR = REPO_ROOT / "corpus" / "calibration"
TRANSCRIPTS_DIR = CAL_DIR / "transcripts"
ARTIFACTS_DIR = REPO_ROOT / "docs" / "artifacts"

# --- Cross-link registry (the four pages + the index) ----------------------------
# (slug, filename, short nav label, one-line hook)
PAGES = [
    ("index", "index.html", "Overview", "The discipline, made visible"),
    ("climbdown", "climbdown.html", "1 · Climb-down",
     "It caught its own propped metric on held-out data"),
    ("spin", "spin_spectrum.html", "2 · Spin spectrum",
     "A 6-level ordinal the field's benchmarks don't have"),
    ("tiebreak", "tiebreak_console.html", "3 · Blind tiebreak",
     "6 disagreements, an independent third read, 4/6 — losses shown"),
    ("debate", "debate_replay.html", "4 · Debate replay",
     "The adversarial triad, replayed from the frozen transcript"),
]
PAGE_FILE = {slug: fn for slug, fn, _, _ in PAGES}


def esc(x) -> str:
    """HTML-escape any value (numbers/None tolerated)."""
    return html.escape("" if x is None else str(x))


def read_json(path: Path):
    with open(path) as fh:
        return json.load(fh)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# --- Palette (dataviz reference instance; validated set) -------------------------
# Kept as CSS custom properties so light/dark swap in one place. Severity ramp
# (fully-supported -> contradicted) uses the reserved status hues good->critical.
_CSS_VARS = """
:root{
  --plane:#f4f4f1; --surface:#fcfcfb; --surface-2:#f6f6f2;
  --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --hair:rgba(11,11,11,.10);
  --accent:#2a78d6; --accent-soft:#e7f0fc;
  --good:#0ca30c; --good-ink:#006300; --warn:#e08e00; --serious:#d5622e; --critical:#c0392b;
  --pos:#1baf7a; --neg:#e34948;
  /* 6-level severity ramp: best -> worst */
  --sev0:#0ca30c; --sev1:#7fae10; --sev2:#e0a500; --sev3:#e07b1f; --sev4:#d4562a; --sev5:#c0392b;
  --code-bg:#f2f1ec;
}
:root[data-theme="dark"]{
  --plane:#0d0d0d; --surface:#1a1a19; --surface-2:#201f1d;
  --ink:#f5f5f0; --ink-2:#c3c2b7; --muted:#8f8d86;
  --grid:#2c2c2a; --axis:#383835; --hair:rgba(255,255,255,.12);
  --accent:#3987e5; --accent-soft:#16233a;
  --good:#0ca30c; --good-ink:#22c55e; --warn:#fab219; --serious:#ec835a; --critical:#e05656;
  --pos:#199e70; --neg:#e66767;
  --sev0:#22b422; --sev1:#8fbf1c; --sev2:#e0a500; --sev3:#e8863a; --sev4:#e0603a; --sev5:#e05656;
  --code-bg:#232220;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --plane:#0d0d0d; --surface:#1a1a19; --surface-2:#201f1d;
    --ink:#f5f5f0; --ink-2:#c3c2b7; --muted:#8f8d86;
    --grid:#2c2c2a; --axis:#383835; --hair:rgba(255,255,255,.12);
    --accent:#3987e5; --accent-soft:#16233a;
    --good-ink:#22c55e; --critical:#e05656;
    --sev0:#22b422; --sev1:#8fbf1c; --sev2:#e0a500; --sev3:#e8863a; --sev4:#e0603a; --sev5:#e05656;
    --code-bg:#232220;
  }
}
"""

_BASE_CSS = """
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--plane);color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-size:16px;line-height:1.55;letter-spacing:.005em}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code,kbd,.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
code{background:var(--code-bg);padding:.08em .38em;border-radius:5px;font-size:.86em}
h1,h2,h3{line-height:1.2;letter-spacing:-.01em;margin:0}
.wrap{max-width:1060px;margin:0 auto;padding:0 22px 96px}
.tnums{font-variant-numeric:tabular-nums}

/* --- top bar / nav --- */
.topbar{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--plane) 86%,transparent);
  backdrop-filter:saturate(1.4) blur(10px);border-bottom:1px solid var(--hair)}
.topbar-in{max-width:1060px;margin:0 auto;padding:9px 22px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{font-weight:750;letter-spacing:-.02em;font-size:15px;white-space:nowrap}
.brand .dot{color:var(--accent)}
.nav{display:flex;gap:3px;flex-wrap:wrap;flex:1}
.nav a{font-size:12.5px;font-weight:560;color:var(--ink-2);padding:5px 9px;border-radius:7px;white-space:nowrap}
.nav a:hover{background:var(--surface-2);text-decoration:none}
.nav a.on{background:var(--accent-soft);color:var(--accent)}
.themetog{border:1px solid var(--hair);background:var(--surface);color:var(--ink-2);
  border-radius:7px;padding:5px 9px;font-size:12px;cursor:pointer;font-weight:600}
.themetog:hover{background:var(--surface-2)}

/* --- hero --- */
.hero{padding:44px 0 10px}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.hero h1{font-size:clamp(27px,4.4vw,42px);font-weight:800;margin:12px 0 0}
.lede{font-size:clamp(16px,1.9vw,19px);color:var(--ink-2);margin:16px 0 0;max-width:70ch}
.kicker{margin-top:16px;font-size:13.5px;color:var(--muted)}
.kicker b{color:var(--ink-2);font-weight:650}

/* --- cards & sections --- */
.card{background:var(--surface);border:1px solid var(--hair);border-radius:14px;
  padding:22px 24px;margin:20px 0;box-shadow:0 1px 0 var(--hair)}
.card h2{font-size:20px;font-weight:750;margin-bottom:4px}
.card h3{font-size:15px;font-weight:700;margin:18px 0 6px}
.sec-note{color:var(--ink-2);font-size:14.5px;margin:6px 0 0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media (max-width:760px){.grid2,.grid3{grid-template-columns:1fr}}

/* --- stat tiles --- */
.tile{background:var(--surface-2);border:1px solid var(--hair);border-radius:12px;padding:15px 17px}
.tile .lab{font-size:11.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.tile .val{font-size:30px;font-weight:800;letter-spacing:-.02em;margin-top:5px;line-height:1}
.tile .sub{font-size:12.5px;color:var(--ink-2);margin-top:6px}

/* --- badges --- */
.badge{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:700;
  padding:2.5px 9px;border-radius:999px;letter-spacing:.02em;white-space:nowrap;vertical-align:middle}
.b-good{background:color-mix(in srgb,var(--good) 16%,transparent);color:var(--good-ink)}
.b-warn{background:color-mix(in srgb,var(--warn) 20%,transparent);color:var(--serious)}
.b-crit{background:color-mix(in srgb,var(--critical) 16%,transparent);color:var(--critical)}
.b-neu{background:var(--surface-2);color:var(--ink-2);border:1px solid var(--hair)}
.b-accent{background:var(--accent-soft);color:var(--accent)}

/* --- bars --- */
.bar-track{position:relative;height:20px;background:var(--surface-2);border:1px solid var(--hair);
  border-radius:6px;overflow:hidden}
.bar-fill{position:absolute;left:0;top:0;bottom:0;border-radius:5px 4px 4px 5px}
.bar-row{display:grid;grid-template-columns:150px 1fr 74px;gap:12px;align-items:center;margin:9px 0}
.bar-row .rl{font-size:13px;color:var(--ink-2);font-weight:600}
.bar-row .rv{font-size:13.5px;font-weight:750;text-align:right}
@media (max-width:560px){.bar-row{grid-template-columns:110px 1fr 56px}}

/* --- tables --- */
table.dt{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:6px}
table.dt th{text-align:left;font-size:11px;letter-spacing:.05em;text-transform:uppercase;
  color:var(--muted);font-weight:700;padding:8px 10px;border-bottom:1px solid var(--axis)}
table.dt td{padding:9px 10px;border-bottom:1px solid var(--grid);vertical-align:top}
table.dt tr:last-child td{border-bottom:none}

/* --- quotes / spans --- */
.span{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;line-height:1.5;
  background:var(--code-bg);border-left:3px solid var(--accent);border-radius:0 7px 7px 0;
  padding:9px 13px;color:var(--ink-2);margin:8px 0}
.callout{border:1px solid var(--hair);border-left:4px solid var(--accent);background:var(--surface-2);
  border-radius:0 10px 10px 0;padding:14px 18px;margin:16px 0}
.callout.warn{border-left-color:var(--warn)}
.callout.crit{border-left-color:var(--critical)}
.small{font-size:12.5px;color:var(--muted)}
.prov{font-size:11.5px;color:var(--muted);font-family:ui-monospace,monospace}
hr.rule{border:none;border-top:1px solid var(--hair);margin:26px 0}

/* --- footer --- */
.foot{border-top:1px solid var(--hair);margin-top:40px;padding-top:20px;color:var(--muted);font-size:12.5px}
.foot a{color:var(--ink-2)}
.foot .xlinks{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.foot .xlinks a{border:1px solid var(--hair);border-radius:8px;padding:6px 11px;font-size:12px;font-weight:600}
.foot .xlinks a:hover{background:var(--surface-2);text-decoration:none}
"""


def _nav(active: str) -> str:
    items = []
    for slug, fn, label, _ in PAGES:
        on = " on" if slug == active else ""
        items.append(f'<a class="navlink{on}" href="{fn}">{esc(label)}</a>')
    return (
        '<div class="topbar"><div class="topbar-in">'
        '<span class="brand">cite<span class="dot">·</span>val</span>'
        f'<nav class="nav">{"".join(items)}</nav>'
        '<button class="themetog" onclick="__toggleTheme()" aria-label="Toggle colour theme">◐ theme</button>'
        '</div></div>'
    )


def _footer(active: str) -> str:
    links = []
    for slug, fn, label, hook in PAGES:
        if slug == active:
            continue
        links.append(f'<a href="{fn}"><b>{esc(label)}</b> — {esc(hook)}</a>')
    return (
        '<footer class="foot">'
        '<div>Built offline from committed data — no model calls, no API key. '
        'Regenerate with <code>python docs/build_artifacts/build_all.py</code>. '
        'Figures trace to the committed calibration corpus, the frozen grade vocabulary, and the '
        'git history each page cites.</div>'
        f'<div class="xlinks">{"".join(links)}</div>'
        '</footer>'
    )


_THEME_JS = """
<script>
(function(){try{var t=localStorage.getItem('citeval-theme');if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}})();
function __toggleTheme(){var r=document.documentElement;var cur=r.getAttribute('data-theme');
 var next = cur==='dark' ? 'light' : (cur==='light' ? 'dark' : (matchMedia('(prefers-color-scheme: dark)').matches?'light':'dark'));
 r.setAttribute('data-theme',next);try{localStorage.setItem('citeval-theme',next);}catch(e){}}
</script>
"""


def page(active: str, title: str, body: str, extra_css: str = "", extra_js: str = "") -> str:
    """Assemble a full, self-contained HTML document."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · citeval</title>
<style>{_CSS_VARS}{_BASE_CSS}{extra_css}</style>
</head>
<body>
{_nav(active)}
<main class="wrap">
{body}
{_footer(active)}
</main>
{_THEME_JS}{extra_js}
</body>
</html>
"""


def hero(eyebrow: str, h1: str, lede: str, kicker: str = "") -> str:
    k = f'<div class="kicker">{kicker}</div>' if kicker else ""
    return (
        f'<section class="hero"><div class="eyebrow">{esc(eyebrow)}</div>'
        f'<h1>{h1}</h1><p class="lede">{lede}</p>{k}</section>'
    )


def tile(label: str, value: str, sub: str = "", val_color: str = "") -> str:
    style = f' style="color:{val_color}"' if val_color else ""
    s = f'<div class="sub">{sub}</div>' if sub else ""
    return (f'<div class="tile"><div class="lab">{esc(label)}</div>'
            f'<div class="val"{style}>{value}</div>{s}</div>')


def write_page(filename: str, html_text: str) -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / filename
    out.write_text(html_text, encoding="utf-8")
    return out


# 6-level ordinal severity metadata, shared by several pages.
SEVERITY = [
    ("fully-supported", "sev0"),
    ("supported-with-overreach", "sev1"),
    ("partially-supported", "sev2"),
    ("technically-true-but-misleading", "sev3"),
    ("unsupported-for-the-claim", "sev4"),
    ("contradicted", "sev5"),
]
SEV_INDEX = {g: i for i, (g, _) in enumerate(SEVERITY)}
SEV_VAR = {g: v for g, v in SEVERITY}


def grade_badge(grade: str) -> str:
    """Render a grade string as a severity-tinted chip; off-scale as neutral."""
    if grade in SEV_VAR:
        var = SEV_VAR[grade]
        return (f'<span class="badge" style="background:color-mix(in srgb,var(--{var}) 17%,transparent);'
                f'color:var(--{var});font-weight:750">{esc(grade)}</span>')
    return f'<span class="badge b-neu">{esc(grade)}</span>'
