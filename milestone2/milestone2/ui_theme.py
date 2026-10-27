"""
ui_theme.py
One place for the app's look.

* inject_theme()  -- global CSS: palette, type, sidebar, tabs, buttons, inputs,
                     and restyles the older class names (.main-title,
                     .stat-card ...) so existing pages pick up the new look.
* *_html()        -- pure functions returning single-line HTML strings for the
                     dashboard-style components (KPI ledger, bars, skill strip,
                     chips, tables). They never touch Streamlit, so they can be
                     previewed/tested on their own. Render with render(html).

Design notes
  Colour carries meaning: teal = skill the candidate has, coral = skill missing,
  amber = waiting on someone, cobalt = primary action / neutral data.
  The skill strip (one segment per required skill) is the signature element.
"""

import html

_esc = html.escape


# ============================================================
# GLOBAL CSS
# ============================================================

THEME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800&family=Instrument+Sans:wght@400;500;600;700&display=swap');

:root{
  --ink:#0F1B2D; --text:#2B3A4F; --muted:#66758A; --line:#E3E8EF; --hair:#EEF1F6;
  --paper:#F4F6F9; --surface:#FFFFFF;
  --cobalt:#2F55D4; --cobalt-dark:#2444B3; --cobalt-soft:#E8EEFD;
  --teal:#0E9F8A; --teal-soft:#E1F4F0; --teal-ink:#0A6B5D;
  --coral:#E5484D; --coral-soft:#FCE9EA; --coral-ink:#B42328;
  --amber:#E39B2D; --amber-soft:#FBF0DC; --amber-ink:#8F5A0B;
  --display:'Bricolage Grotesque','Segoe UI',system-ui,sans-serif;
  --body:'Instrument Sans','Segoe UI',system-ui,sans-serif;
}

/* ---------- canvas ---------- */
.stApp{background:var(--paper);font-family:var(--body);color:var(--text)}
.stApp .main,.stApp [data-testid="stMain"]{background:transparent}
.stApp [data-testid="stHeader"]{background:transparent}
.stApp .block-container{padding-top:2.2rem;padding-bottom:3rem;max-width:1360px}
.stApp p,.stApp label,.stApp li,.stApp input,.stApp textarea,.stApp button,
.stApp [data-testid="stMarkdownContainer"],.stApp [data-baseweb="tab"]{font-family:var(--body)}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5{font-family:var(--display);color:var(--ink);letter-spacing:-.01em}

/* ---------- sidebar ---------- */
.stApp section[data-testid="stSidebar"]{background:var(--ink);border-right:0}
.stApp section[data-testid="stSidebar"] *{color:#C9D4E5}
.stApp section[data-testid="stSidebar"] h3{font-size:15px;color:#fff}
.stApp section[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,.1)}
.stApp section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{font-size:12px;color:#7D8CA3}
.stApp section[data-testid="stSidebar"] div[role="radiogroup"]{gap:2px}
.stApp section[data-testid="stSidebar"] div[role="radiogroup"] > label{
  padding:9px 12px 9px 12px;border-radius:8px;border-left:3px solid transparent;margin:0;width:100%;cursor:pointer}
.stApp section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child{display:none}
.stApp section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover{background:rgba(255,255,255,.06)}
.stApp section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked){
  background:rgba(143,176,255,.15);border-left-color:#8FB0FF}
.stApp section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p{color:#fff;font-weight:600}
.stApp section[data-testid="stSidebar"] button{
  background:transparent;border:1px solid rgba(255,255,255,.22);color:#E6EDF8;border-radius:10px}
.stApp section[data-testid="stSidebar"] button:hover{background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.4);color:#fff}
.brand{display:flex;align-items:center;gap:11px;margin:2px 0 24px}
.brand-mark{position:relative;flex:0 0 34px;width:34px;height:34px;border-radius:9px;background:var(--cobalt)}
.brand-mark::before,.brand-mark::after{content:"";position:absolute;top:10px;width:14px;height:14px;border-radius:50%;border:2.5px solid #fff}
.brand-mark::before{left:6px}
.brand-mark::after{left:14px;border-color:#7FE6D2}
.stApp section[data-testid="stSidebar"] .brand-name{font-family:var(--display);font-weight:800;font-size:16px;color:#fff;line-height:1.15;white-space:nowrap}
.stApp section[data-testid="stSidebar"] .brand-sub{font-size:11.5px;color:#7D8CA3;margin-top:2px}

/* ---------- native widgets ---------- */
.stApp [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--line)}
.stApp button[data-baseweb="tab"]{padding:10px 14px;font-weight:600;color:var(--muted)}
.stApp button[data-baseweb="tab"][aria-selected="true"]{color:var(--cobalt)}
.stApp [data-baseweb="tab-highlight"]{background:var(--cobalt);height:2px}
.stApp [data-baseweb="tab-border"]{display:none}

.stApp [data-testid="stBaseButton-primary"],.stApp button[kind="primary"],.stApp button[kind="primaryFormSubmit"]{
  background:var(--cobalt);border:1px solid var(--cobalt);color:#fff;border-radius:10px;font-weight:600}
.stApp [data-testid="stBaseButton-primary"]:hover,.stApp button[kind="primary"]:hover,.stApp button[kind="primaryFormSubmit"]:hover{
  background:var(--cobalt-dark);border-color:var(--cobalt-dark);color:#fff}
.stApp [data-testid="stBaseButton-secondary"],.stApp button[kind="secondary"],.stApp button[kind="secondaryFormSubmit"],
.stApp [data-testid="stDownloadButton"] button{
  background:#fff;border:1px solid #CBD3DF;color:var(--ink);border-radius:10px;font-weight:600}
.stApp [data-testid="stBaseButton-secondary"]:hover,.stApp button[kind="secondary"]:hover,
.stApp [data-testid="stDownloadButton"] button:hover{border-color:var(--cobalt);color:var(--cobalt)}

.stApp [data-baseweb="input"],.stApp [data-baseweb="textarea"],.stApp [data-baseweb="select"] > div{
  border-radius:10px;border-color:#CBD3DF;background:#fff}
.stApp [data-baseweb="input"]:focus-within,.stApp [data-baseweb="textarea"]:focus-within{
  border-color:var(--cobalt);box-shadow:0 0 0 3px rgba(47,85,212,.14)}
.stApp [data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:12px;overflow:hidden}
.stApp [data-testid="stExpander"]{background:#fff;border:1px solid var(--line);border-radius:12px}
.stApp [data-testid="stAlert"]{border-radius:12px}
.stApp [data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 16px}

/* ---------- legacy classes used by the older pages ---------- */
.stApp .main-title{font-family:var(--display);font-size:32px;font-weight:800;letter-spacing:-.02em;color:var(--ink);margin-bottom:4px}
.stApp .subtitle{color:var(--muted);font-size:15px;margin-bottom:22px}
.stApp .section-title{font-family:var(--display);font-weight:700;color:var(--ink)}
.stApp .card{background:#fff;border:1px solid var(--line);border-radius:14px}
.stApp .stat-card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 20px;text-align:left;height:auto;min-height:104px}
.stApp .stat-label{color:var(--muted);font-size:13px;text-transform:none;letter-spacing:0;font-weight:600}
.stApp .stat-value{font-family:var(--display);font-size:32px;font-weight:800;color:var(--ink);margin-top:6px}
.stApp .skill-badge{background:var(--cobalt-soft);color:var(--cobalt-dark);border-radius:999px;padding:4px 11px;font-size:12.5px;font-weight:600}
.stApp .candidate-row{background:#fff;border:1px solid var(--line);border-radius:12px}
.stApp .status-pill{background:var(--teal-soft);color:var(--teal-ink);border-radius:999px;font-weight:700}

/* ---------- page header ---------- */
.page-head{margin:0 0 22px}
.page-title{font-family:var(--display);font-size:34px;font-weight:800;letter-spacing:-.02em;color:var(--ink);line-height:1.08}
.page-sentence{font-size:15px;color:var(--muted);margin:9px 0 0;max-width:70ch;line-height:1.5}

/* ---------- KPI ledger: one band, not five cards ---------- */
.ledger{display:grid;grid-template-columns:repeat(auto-fit,minmax(176px,1fr));background:var(--surface);
  border:1px solid var(--line);border-radius:14px;overflow:hidden;margin:0 0 18px;box-shadow:0 1px 2px rgba(15,27,45,.04)}
.ledger .cell{min-width:0;padding:18px 22px;box-shadow:1px 0 0 var(--line),0 1px 0 var(--line)}
.ledger .num{font-family:var(--display);font-size:36px;font-weight:800;letter-spacing:-.02em;color:var(--ink);line-height:1;
  font-variant-numeric:tabular-nums}
.ledger .num.txt{font-size:22px;line-height:1.25;padding-top:7px;overflow-wrap:anywhere}
.ledger .lbl{font-size:14px;font-weight:600;color:var(--text);margin-top:9px}
.ledger .hint{font-size:12.5px;color:var(--muted);margin-top:3px;line-height:1.4}
.ledger .hint.ok{color:var(--teal-ink)} .ledger .hint.warn{color:var(--amber-ink)} .ledger .hint.bad{color:var(--coral-ink)}

/* ---------- panels ---------- */
.panel{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px 24px;margin:0 0 18px;
  box-shadow:0 1px 2px rgba(15,27,45,.04)}
.panel-title{font-family:var(--display);font-size:18px;font-weight:700;color:var(--ink);letter-spacing:-.01em}
.panel-cap{font-size:13px;color:var(--muted);margin:3px 0 16px;line-height:1.45}
.grid{display:grid;gap:18px;margin:0 0 18px}
.grid.g32{grid-template-columns:3fr 2fr}
.grid > .panel{margin:0}
.split{display:grid;grid-template-columns:1fr 1fr}
.split > div:first-child{padding-right:26px}
.split > div + div{padding-left:26px;border-left:1px solid var(--line)}
.subhead{font-size:13.5px;font-weight:700;color:var(--ink);margin:0 0 12px}
.muted{color:var(--muted)}
@media (max-width:980px){
  .grid.g32,.split{grid-template-columns:1fr}
  .split > div:first-child{padding-right:0}
  .split > div + div{padding-left:0;border-left:0;border-top:1px solid var(--line);margin-top:18px;padding-top:18px}
}

/* ---------- insights ---------- */
.insights{display:grid;gap:11px}
.insight{display:flex;gap:12px;font-size:14.5px;line-height:1.5;color:var(--text)}
.insight::before{content:"";flex:0 0 4px;border-radius:2px;background:var(--cobalt)}
.insight.ok::before{background:var(--teal)} .insight.bad::before{background:var(--coral)} .insight.warn::before{background:var(--amber)}
.insight b{color:var(--ink)}

/* ---------- horizontal bars ---------- */
.bars{display:flex;flex-direction:column;gap:11px}
.bar-row{display:grid;grid-template-columns:minmax(96px,170px) 1fr 92px;align-items:center;gap:12px}
.bar-label{font-size:13.5px;font-weight:500;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-track{height:12px;background:var(--hair);border-radius:4px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px;background:var(--cobalt)}
.bar-fill.teal{background:var(--teal)} .bar-fill.coral{background:var(--coral)} .bar-fill.amber{background:var(--amber)}
.bar-val{font-family:var(--display);font-size:15px;font-weight:700;color:var(--ink);text-align:right;font-variant-numeric:tabular-nums}
.bar-val small{font-family:var(--body);font-size:11.5px;font-weight:500;color:var(--muted);margin-left:4px}

/* ---------- vertical columns ---------- */
.cols{display:flex;align-items:flex-end;gap:14px;padding-top:6px}
.col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end}
.col-num{font-family:var(--display);font-size:15px;font-weight:700;color:var(--ink);margin-bottom:6px}
.col-bar{width:100%;max-width:60px;border-radius:5px 5px 0 0;background:var(--cobalt);min-height:3px}
.col-bar.teal{background:var(--teal)} .col-bar.coral{background:var(--coral)} .col-bar.amber{background:var(--amber)}
.col-lbl{font-size:12.5px;color:var(--muted);margin-top:9px;white-space:nowrap}

/* ---------- stacked status bar ---------- */
.stack{display:flex;gap:3px;height:14px}
.stack > span{display:block;height:100%;border-radius:4px;min-width:6px}
.legend{display:flex;flex-wrap:wrap;gap:26px;margin-top:20px}
.legend .n{font-family:var(--display);font-size:30px;font-weight:800;color:var(--ink);line-height:1;font-variant-numeric:tabular-nums}
.legend .t{display:flex;align-items:center;gap:7px;font-size:13px;color:var(--muted);margin-top:6px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%}

/* ---------- THE signature element: skill strip ---------- */
.strip{display:flex;gap:3px;height:10px;min-width:90px}
.strip > i{flex:1;border-radius:3px;background:var(--teal)}
.strip > i.miss{background:var(--coral)}
.strip.lg{height:16px;gap:5px}
.strip.lg > i{border-radius:4px}
.key{display:flex;gap:18px;font-size:12.5px;color:var(--muted);margin-top:10px}
.key span{display:flex;align-items:center;gap:6px}

/* ---------- chips + pills ---------- */
.chip{display:inline-flex;align-items:center;border-radius:999px;padding:3px 11px;margin:2px 5px 2px 0;font-size:12.5px;font-weight:600;line-height:1.5}
.chip.ok{background:var(--teal-soft);color:var(--teal-ink)}
.chip.bad{background:var(--coral-soft);color:var(--coral-ink)}
.chip.neutral{background:var(--hair);color:var(--text)}
.pill{display:inline-block;border-radius:999px;padding:3px 11px;font-size:12px;font-weight:700}
.pill.ok{background:var(--teal-soft);color:var(--teal-ink)}
.pill.warn{background:var(--amber-soft);color:var(--amber-ink)}
.pill.bad{background:var(--coral-soft);color:var(--coral-ink)}
.pill.neutral{background:var(--cobalt-soft);color:var(--cobalt-dark)}

/* ---------- tables ---------- */
.tbl-wrap{overflow-x:auto}
.tbl{width:100%;border-collapse:collapse;font-size:13.5px}
.tbl th{text-align:left;font-size:12.5px;font-weight:600;color:var(--muted);padding:0 14px 10px 0;border-bottom:1px solid var(--line);white-space:nowrap}
.tbl td{padding:12px 14px 12px 0;border-bottom:1px solid var(--hair);vertical-align:middle;color:var(--text)}
.tbl tr:last-child td{border-bottom:0}
.tbl .name{font-weight:600;color:var(--ink)}
.tbl .sub{color:var(--muted);font-size:12.5px;margin-top:1px}
.tbl .figure{font-family:var(--display);font-weight:700;font-size:15px;color:var(--ink);font-variant-numeric:tabular-nums}
.tbl .cov{display:flex;align-items:center;gap:12px;min-width:200px}
.tbl .cov .strip{flex:1}

/* ---------- candidate list (skill gap page) ---------- */
.cand{display:grid;grid-template-columns:minmax(150px,1.1fr) 2fr 64px 120px;gap:20px;align-items:center;
  padding:14px 0;border-bottom:1px solid var(--hair)}
.cand:first-child{padding-top:2px}
.cand:last-child{border-bottom:0;padding-bottom:2px}
.cand .name{font-weight:600;color:var(--ink);font-size:14.5px}
.cand .sub{color:var(--muted);font-size:12.5px;margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cand .pct{font-family:var(--display);font-weight:800;font-size:22px;color:var(--ink);text-align:right;font-variant-numeric:tabular-nums}
.cand .gaps{font-size:12.5px;color:var(--muted)}
@media (max-width:760px){.cand{grid-template-columns:1fr 64px}.cand .strip{grid-column:1 / -1}.cand .gaps{display:none}}

/* ---------- detail header ---------- */
.detail-head{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;flex-wrap:wrap;margin-bottom:18px}
.detail-name{font-family:var(--display);font-size:24px;font-weight:800;color:var(--ink);letter-spacing:-.01em;line-height:1.15}
.detail-pct{font-family:var(--display);font-size:46px;font-weight:800;color:var(--ink);line-height:1;letter-spacing:-.02em;text-align:right}
.detail-pct small{display:block;font-family:var(--body);font-size:12.5px;font-weight:500;color:var(--muted);letter-spacing:0;margin-top:6px}
.trio{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:22px;margin-top:22px}
.trio .subhead{margin-bottom:8px}

/* ---------- empty state ---------- */
.empty{border:1px dashed #CBD3DF;border-radius:10px;padding:16px 18px;background:#FAFBFD;color:var(--muted);font-size:13.5px;line-height:1.5}
.empty b{display:block;color:var(--ink);font-size:14px;margin-bottom:2px}
"""


def inject_theme():
    """Call once per run, after the login gate and before any page content."""
    import streamlit as st
    st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)


def render(markup: str):
    import streamlit as st
    st.markdown(markup, unsafe_allow_html=True)


# ============================================================
# HTML BUILDERS (pure, single-line output -- Streamlit's markdown turns blank
# lines / 4-space indents inside HTML into code blocks, so never emit them)
# ============================================================

def _tone(tone):
    return tone if tone in ("ok", "warn", "bad", "neutral") else ""


def _num(value) -> str:
    """Whole-number display for counts and percentages."""
    try:
        return str(int(round(float(value))))
    except (TypeError, ValueError):
        return str(value)


def brand_html() -> str:
    return (
        '<div class="brand"><div class="brand-mark"></div>'
        '<div><div class="brand-name">Recruitment Copilot</div>'
        '<div class="brand-sub">Hiring workspace</div></div></div>'
    )


def page_header_html(title: str, sentence: str = "") -> str:
    s = f'<div class="page-sentence">{_esc(sentence)}</div>' if sentence else ""
    return f'<div class="page-head"><div class="page-title">{_esc(title)}</div>{s}</div>'


def ledger_html(items) -> str:
    """items: list of dicts {value, label, hint, tone, text}. text=True renders the
    value as a short phrase (e.g. a skill name) instead of a big number."""
    cells = []
    for it in items:
        num_cls = "num txt" if it.get("text") else "num"
        hint = ""
        if it.get("hint"):
            hint = f'<div class="hint {_tone(it.get("tone"))}">{_esc(str(it["hint"]))}</div>'
        cells.append(
            f'<div class="cell"><div class="{num_cls}">{_esc(str(it["value"]))}</div>'
            f'<div class="lbl">{_esc(it["label"])}</div>{hint}</div>'
        )
    return f'<div class="ledger">{"".join(cells)}</div>'


def panel_html(title: str, caption: str, body: str) -> str:
    cap = f'<div class="panel-cap">{_esc(caption)}</div>' if caption else '<div class="panel-cap"></div>'
    return f'<div class="panel"><div class="panel-title">{_esc(title)}</div>{cap}{body}</div>'


def split_html(left: str, right: str) -> str:
    return f'<div class="split"><div>{left}</div><div>{right}</div></div>'


def subhead_html(text: str) -> str:
    return f'<div class="subhead">{_esc(text)}</div>'


def empty_html(title: str, hint: str = "") -> str:
    return f'<div class="empty"><b>{_esc(title)}</b>{_esc(hint)}</div>'


def insights_html(items) -> str:
    """items: list of (tone, text). Text may contain <b> from trusted callers only,
    so callers must escape user data themselves with esc()."""
    rows = "".join(f'<div class="insight {_tone(t)}"><div>{txt}</div></div>' for t, txt in items)
    return f'<div class="insights">{rows}</div>'


def esc(text) -> str:
    return _esc(str(text))


def bars_html(rows, tone: str = "", max_value=None) -> str:
    """rows: (label, value) or (label, value, extra_text) or (label, value, extra, tone)."""
    if not rows:
        return ""
    top = max_value or max(max(float(r[1]) for r in rows), 1.0)
    out = []
    for r in rows:
        label, value = r[0], float(r[1])
        extra = r[2] if len(r) > 2 and r[2] else ""
        row_tone = r[3] if len(r) > 3 and r[3] else tone
        width = 0.0 if value <= 0 else max(2.0, min(100.0, value / top * 100))
        extra_html = f"<small>{_esc(str(extra))}</small>" if extra else ""
        out.append(
            f'<div class="bar-row"><div class="bar-label" title="{_esc(str(label))}">{_esc(str(label))}</div>'
            f'<div class="bar-track"><div class="bar-fill {row_tone}" style="width:{width:.1f}%"></div></div>'
            f'<div class="bar-val">{_num(value)}{extra_html}</div></div>'
        )
    return f'<div class="bars">{"".join(out)}</div>'


def columns_html(rows, tone: str = "", plot_height: int = 150) -> str:
    """rows: (label, value) or (label, value, tone). Vertical histogram with the
    value on top of each bar."""
    top = max(max(float(r[1]) for r in rows), 1.0)
    cols = []
    for r in rows:
        label, value = r[0], float(r[1])
        col_tone = r[2] if len(r) > 2 and r[2] else tone
        h = 3 if value <= 0 else max(6, int(value / top * plot_height))
        cols.append(
            f'<div class="col"><div class="col-num">{_num(value)}</div>'
            f'<div class="col-bar {col_tone}" style="height:{h}px"></div>'
            f'<div class="col-lbl">{_esc(str(label))}</div></div>'
        )
    return f'<div class="cols">{"".join(cols)}</div>'


def stacked_html(segments) -> str:
    """segments: (label, value, css_colour). One segmented bar plus a legend of counts."""
    total = sum(float(v) for _, v, _ in segments)
    if total <= 0:
        return ""
    bar = "".join(
        f'<span style="flex:{float(v)};background:{c}" title="{_esc(l)}: {_num(v)}"></span>'
        for l, v, c in segments if float(v) > 0
    )
    legend = "".join(
        f'<div><div class="n">{_num(v)}</div>'
        f'<div class="t"><span class="dot" style="background:{c}"></span>{_esc(l)}</div></div>'
        for l, v, c in segments
    )
    return f'<div class="stack">{bar}</div><div class="legend">{legend}</div>'


def strip_html(required, matched, large: bool = False) -> str:
    """One segment per required skill: teal if the candidate has it, coral if not."""
    have = {s.lower() for s in matched}
    segs = "".join(
        f'<i class="{"" if s.lower() in have else "miss"}" '
        f'title="{_esc(s)}: {"has it" if s.lower() in have else "missing"}"></i>'
        for s in required
    )
    return f'<div class="strip{" lg" if large else ""}">{segs}</div>'


def strip_key_html() -> str:
    return (
        '<div class="key"><span><i class="dot" style="background:var(--teal)"></i>Has the skill</span>'
        '<span><i class="dot" style="background:var(--coral)"></i>Missing</span></div>'
    )


def chips_html(skills, kind: str = "neutral") -> str:
    if not skills:
        return '<span class="muted">None</span>'
    return "".join(f'<span class="chip {kind}">{_esc(str(s))}</span>' for s in skills)


def pill_html(text: str, tone: str = "neutral") -> str:
    return f'<span class="pill {_tone(tone) or "neutral"}">{_esc(text)}</span>'


def table_html(headers, rows) -> str:
    """headers: list of str. rows: list of lists of ready-made HTML cell strings."""
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def name_cell_html(name: str, sub: str = "") -> str:
    s = f'<div class="sub">{_esc(sub)}</div>' if sub else ""
    return f'<div class="name">{_esc(name)}</div>{s}'


def candidate_rows_html(rows) -> str:
    """rows: dicts with name, email, required, matched, coverage, missing_count."""
    out = []
    for r in rows:
        gaps = "No gaps" if not r["missing_count"] else f'{r["missing_count"]} missing'
        out.append(
            f'<div class="cand"><div><div class="name">{_esc(r["name"])}</div>'
            f'<div class="sub">{_esc(r.get("email") or "")}</div></div>'
            f'{strip_html(r["required"], r["matched"])}'
            f'<div class="pct">{_num(r["coverage"])}%</div>'
            f'<div class="gaps">{gaps}</div></div>'
        )
    return "".join(out)