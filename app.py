import re
from pathlib import Path
import html
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ----------------------------
# Page config (no sidebar, wall-screen friendly)
# ----------------------------
st.set_page_config(
    page_title="Int-Ops Dashboard",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st_autorefresh(interval=15 * 60 * 1000, key="auto_refresh_15min")  # 15 minutes

# ----------------------------
# Low-glare dark styling + larger headers/status + tighter spacing
# ----------------------------
CSS = """
<style>
  .stApp { background: #0b0f14; color: #e6edf3; }
  header, footer { visibility: hidden; height: 0px; }
  [data-testid="stSidebar"] { display: none; }

  html, body, [class*="css"]  {
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
  }

  .topbar {
    background: #0f1620;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 12px 14px;
    margin-bottom: 10px;
  }
  .title { font-size: 28px; font-weight: 900; margin: 0; line-height: 1.1; }
  .meta  { margin-top: 6px; font-size: 13px; color: rgba(230,237,243,0.75); }

  .section-title { font-size: 20px; font-weight: 900; margin: 6px 0 8px 0; }

  .card {
    background: #0f1620;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 10px 12px 10px 12px;
    margin-bottom: 8px;
  }
  .name { font-size: 19px; font-weight: 950; margin: 0; line-height: 1.1; }
  .statusline { margin-top: 4px; font-size: 16px; font-weight: 950; letter-spacing: 0.2px; }
  .notes { margin-top: 6px; font-size: 12.5px; color: rgba(230,237,243,0.92); line-height: 1.28; }

  .status-open      { color: rgba(82,196,26,1.0); }
  .status-closed    { color: rgba(255,77,79,1.0); }
  .status-partial   { color: rgba(255,169,64,1.0); }
  .status-restrict  { color: rgba(250,219,20,1.0); }

  /* Incident chips */
  .chip-wrap { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  .chip {
    display: inline-flex;
    align-items: center;
    padding: 8px 10px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.10);
    background: rgba(255,255,255,0.04);
    font-size: 16px;
    font-weight: 950;
    letter-spacing: 0.2px;
    white-space: nowrap;
  }
  .chip-active {
    border-color: rgba(255,77,79,0.55);
    background: rgba(255,77,79,0.12);
  }
  .chip-clear {
    border-color: rgba(82,196,26,0.45);
    background: rgba(82,196,26,0.10);
  }

  /* Airport rows */
  .airport-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: baseline;
    padding: 8px 0;
    border-top: 1px solid rgba(255,255,255,0.06);
  }
  .airport-row:first-of-type { border-top: none; }
  .airport-name { font-size: 15px; font-weight: 900; line-height: 1.15; }
  .airport-status { font-size: 16px; font-weight: 950; letter-spacing: 0.2px; }
  .airport-open { color: rgba(82,196,26,1.0); }
  .airport-closed { color: rgba(255,77,79,1.0); }
  .airport-partial { color: rgba(255,169,64,1.0); }
  .airport-unknown { color: rgba(230,237,243,0.75); }

  div[data-testid="column"] { padding-top: 0px; }
  .block-container { padding-top: 1.0rem; padding-bottom: 0.8rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Truth: exact border headers
# ----------------------------
BORDER_HEADERS = [
    "UAE-Oman",
    "UAE-Saudi Arabia",
    "Israel-Egypt",
    "Israel-Jordan",
    "Iran-Turkiye",
    "Iran-Armenia",
]

# ----------------------------
# Helpers
# ----------------------------
def load_update(path="update.txt") -> str:
    p = Path(path)
    if not p.exists():
        st.error(f"Missing {path}. Create it and paste your bulletin text.")
        st.stop()
    return p.read_text(encoding="utf-8", errors="ignore")

def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"(?m)^\s*-{6,}\s*$", "------------------", text)  # normalize separators
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text

def status_class(status: str) -> str:
    s = (status or "").strip().lower()
    if s == "closed": return "status-closed"
    if s == "partial": return "status-partial"
    if s in ("restricted", "restrict", "restriction"): return "status-restrict"
    if s == "open": return "status-open"
    return ""

def capitalize_first_alpha(s: str) -> str:
    if not s:
        return ""
    chars = list(s)
    for i, ch in enumerate(chars):
        if ch.isalpha():
            chars[i] = ch.upper()
            break
    return "".join(chars)

def clamp_text(s: str, max_len: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= max_len else s[: max_len - 1].rstrip() + "…"

def infer_status_from_text(text: str) -> str:
    t = (text or "").lower()
    open_hit = bool(re.search(r"\bopen\b|\bremains open\b", t))
    closed_hit = bool(re.search(r"\bclosed\b|\breportedly closed\b|\ball other\b.*\bclosed\b", t))
    partial_hit = bool(re.search(r"\bpartial\b", t))
    restrict_hit = "restrict" in t

    if partial_hit:
        return "partial"
    if open_hit and (closed_hit or restrict_hit):
        return "partial"
    if restrict_hit:
        return "restricted"
    if closed_hit:
        return "closed"
    if open_hit:
        return "open"
    return ""

def render_card(
    name: str,
    status: str,
    bullets: list[str],
    *,
    show_placeholder: bool = True,
    max_bullets: int = 3,
    max_bullet_len: int = 180,
    truncate: bool = True,
):
    name = (name or "").strip()
    status = (status or "").strip().lower()

    s_cls = status_class(status)
    status_html = f'<div class="statusline {s_cls}">{status.upper()}</div>' if status else ""

    bullets = [b.strip() for b in (bullets or []) if b and b.strip()]
    bullets = bullets[:max_bullets]
    if truncate:
        bullets = [clamp_text(b, max_bullet_len) for b in bullets]

    if bullets:
        notes_html = "<br/>".join([f"• {html.escape(b)}" for b in bullets])
        notes_html = f'<div class="notes">{notes_html}</div>'
    else:
        notes_html = '<div class="notes">• —</div>' if show_placeholder else ""

    st.markdown(
        f"""
        <div class="card">
          <div class="name">{html.escape(name)}</div>
          {status_html}
          {notes_html}
        </div>
        """,
        unsafe_allow_html=True
    )

def split_blocks_4(raw: str):
    """
    update.txt:
      1) Borders
      ------------------
      2) Airspace
      ------------------
      3) Incident lists
      ------------------
      4) Key airports
    """
    parts = [p.strip() for p in raw.split("------------------")]
    parts = [p for p in parts if p]

    borders_block   = parts[0] if len(parts) >= 1 else ""
    airspace_block  = parts[1] if len(parts) >= 2 else ""
    incidents_block = parts[2] if len(parts) >= 3 else ""
    airports_block  = parts[3] if len(parts) >= 4 else ""
    return borders_block, airspace_block, incidents_block, airports_block

# ----------------------------
# Parsing: Borders (exact headers)
# ----------------------------
def parse_borders(block: str):
    lines = [ln.strip() for ln in block.split("\n")]
    idxs = [(i, ln) for i, ln in enumerate(lines) if ln in BORDER_HEADERS]

    items = []
    for n, (start_i, header) in enumerate(idxs):
        end_i = idxs[n + 1][0] if n + 1 < len(idxs) else len(lines)
        body_lines = [l.strip() for l in lines[start_i + 1:end_i] if l.strip()]
        body_text = " ".join(body_lines).strip()

        status = infer_status_from_text(body_text)

        bullets = []
        if body_text:
            parts = re.split(r"(?<=[.!?])\s+", body_text)
            for p in parts:
                p = p.strip()
                if p:
                    bullets.append(p)
                if len(bullets) >= 3:
                    break

        items.append({"name": header, "status": status, "bullets": bullets})

    if not items:
        items.append({
            "name": "Borders (format issue)",
            "status": "",
            "bullets": ["Could not detect border headers. Ensure exact header lines are used."]
        })
    return items

# ----------------------------
# Parsing: Airspace (Country status; optional notes after ';')
# ----------------------------
def parse_airspace(block: str):
    lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
    if lines and lines[0].strip().upper() == "AIRSPACE":
        lines = lines[1:]

    items = []
    for ln in lines:
        main, sep, tail = ln.partition(";")
        main = main.strip()
        notes = tail.strip() if sep else ""

        m = re.match(r"^(?P<country>.+?)\s+(?P<status>open|closed|partial)\b(?P<rest>.*)$", main, flags=re.I)
        if not m:
            items.append({"country": ln, "status": "", "notes": ""})
            continue

        country = m.group("country").strip()
        status = m.group("status").strip().lower()
        rest = (m.group("rest") or "").strip()

        if rest:
            rest = rest.lstrip(" -–—:").strip()
            if rest:
                notes = (rest + ((" " + notes) if notes else "")).strip()

        notes = capitalize_first_alpha(notes)
        if notes.lower().strip(". ") == country.lower().strip(". "):
            notes = ""

        items.append({"country": country, "status": status, "notes": notes})

    if not items:
        items.append({"country": "Airspace (no entries)", "status": "", "notes": ""})
    return items

# ----------------------------
# Parsing: Incident lists (block #3)
# ----------------------------
def parse_incident_lists(block: str):
    def norm(s: str) -> str:
        s = s.replace("\u00a0", " ")
        return re.sub(r"\s+", " ", s).strip().lower()

    lines = [ln.strip() for ln in block.split("\n")]
    active, inactive = [], []
    mode = None

    for ln in lines:
        if not ln:
            continue
        n = norm(ln)

        if n in ("active incidents in past 1h", "active incidents (past 1h)"):
            mode = "active"
            continue
        if n == "no active incidents":
            mode = "inactive"
            continue

        if mode == "active":
            active.append(ln)
        elif mode == "inactive":
            inactive.append(ln)

    active = sorted({c.strip() for c in active if c.strip()}, key=str.casefold)
    inactive = sorted({c.strip() for c in inactive if c.strip()}, key=str.casefold)
    return active, inactive

def render_chips(title: str, items: list[str], *, variant: str):
    cls = "chip-active" if variant == "active" else "chip-clear"
    chips = "".join([f'<span class="chip {cls}">{html.escape(c)}</span>' for c in items])
    empty = '<div class="notes">—</div>' if not items else ""
    st.markdown(
        f"""
        <div class="card">
          <div class="name">{html.escape(title)}</div>
          <div class="chip-wrap">{chips}</div>
          {empty}
        </div>
        """,
        unsafe_allow_html=True
    )

# ----------------------------
# Parsing: Key Airports (block #4)
# ----------------------------
def parse_key_airports(block: str):
    lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
    if not lines:
        return []
    if lines and lines[0].strip().lower() == "key airports":
        lines = lines[1:]

    airports = []
    for ln in lines:
        if ":" in ln:
            a_name, a_status = ln.split(":", 1)
            airports.append((a_name.strip(), a_status.strip()))
        else:
            airports.append((ln.strip(), ""))
    return airports

def render_airports(airports: list[tuple[str, str]]):
    rows_html = []
    for a_name, a_status in airports:
        s = (a_status or "").strip().lower()
        cls = "airport-unknown"
        label = a_status.strip() if a_status else "—"
        if s.startswith("open"):
            cls = "airport-open"
            label = "OPEN"
        elif s.startswith("closed"):
            cls = "airport-closed"
            label = "CLOSED"
        elif s.startswith("partial"):
            cls = "airport-partial"
            label = "PARTIAL"

        rows_html.append(
            f"""
            <div class="airport-row">
              <div class="airport-name">{html.escape(a_name)}</div>
              <div class="airport-status {cls}">{html.escape(label)}</div>
            </div>
            """
        )

    body = "\n".join(rows_html) if rows_html else '<div class="notes" style="margin-top:10px;">—</div>'

    st.markdown(
        f"""
        <div class="card">
          <div class="name">Key Airports</div>
          {body}
        </div>
        """,
        unsafe_allow_html=True
    )

# ----------------------------
# Load + parse
# ----------------------------
raw = normalize(load_update("update.txt"))
borders_block, airspace_block, incidents_block, airports_block = split_blocks_4(raw)

borders = parse_borders(borders_block)
airspace = parse_airspace(airspace_block)
active_countries, inactive_countries = parse_incident_lists(incidents_block)
key_airports = parse_key_airports(airports_block)

# As-of detector (matches "As of March 3")
as_of = ""
m_asof = re.search(r"(?i)\bas of\s+([A-Za-z]+\s+\d{1,2})", raw)
if m_asof:
    as_of = m_asof.group(1)

# ----------------------------
# Header
# ----------------------------
st.markdown(
    f"""
    <div class="topbar">
      <div class="title">Middle East - Status</div>
      <div class="meta"><b>AS OF:</b> {html.escape(as_of) if as_of else "—"}</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ----------------------------
# Layout
# ----------------------------
c1, c2, c3 = st.columns([1.25, 1.0, 1.0], gap="large")

with c1:
    st.markdown('<div class="section-title">LAND BORDERS</div>', unsafe_allow_html=True)
    for b in borders:
        render_card(
            b["name"],
            b["status"],
            b["bullets"],
            show_placeholder=True,
            max_bullets=3,
            max_bullet_len=210,
            truncate=True
        )

with c2:
    st.markdown('<div class="section-title">AIRSPACE</div>', unsafe_allow_html=True)
    a_left, a_right = st.columns(2, gap="small")
    for idx, a in enumerate(airspace):
        bullets = [a["notes"]] if a.get("notes") else []
        target = a_left if idx % 2 == 0 else a_right
        with target:
            render_card(
                a["country"],
                a["status"],
                bullets,
                show_placeholder=False,
                max_bullets=1,
                max_bullet_len=140,
                truncate=True
            )

with c3:
    st.markdown('<div class="section-title">INCIDENT STATUS</div>', unsafe_allow_html=True)
    render_chips("Active Incidents (past 1H)", active_countries, variant="active")
    render_chips("No Active Incidents", inactive_countries, variant="clear")

    st.markdown('<div class="section-title">KEY AIRPORTS</div>', unsafe_allow_html=True)
    render_airports(key_airports)
