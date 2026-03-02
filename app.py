import re
from pathlib import Path
import streamlit as st

# ----------------------------
# Page config (no sidebar, wall-screen friendly)
# ----------------------------
st.set_page_config(
    page_title="Int-Ops Dashboard",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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
    padding: 10px 12px 8px 12px;
    margin-bottom: 8px;
  }
  .name { font-size: 19px; font-weight: 950; margin: 0; line-height: 1.1; }
  .statusline { margin-top: 4px; font-size: 16px; font-weight: 950; letter-spacing: 0.2px; }
  .notes { margin-top: 6px; font-size: 12.5px; color: rgba(230,237,243,0.92); line-height: 1.28; }

  .status-open      { color: rgba(82,196,26,1.0); }
  .status-closed    { color: rgba(255,77,79,1.0); }
  .status-partial   { color: rgba(255,169,64,1.0); }
  .status-restrict  { color: rgba(250,219,20,1.0); }

  /* Make Streamlit columns slightly tighter */
  div[data-testid="column"] { padding-top: 0px; }

  /* Slightly reduce default block spacing */
  .block-container { padding-top: 1.0rem; padding-bottom: 0.8rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Your declared "truth"
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
    # normalize dashed separators: any line with 6+ dashes becomes the delimiter token
    text = re.sub(r"(?m)^\s*-{6,}\s*$", "------------------", text)
    # collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text

def status_class(status: str) -> str:
    s = (status or "").strip().lower()
    if s == "closed":
        return "status-closed"
    if s == "partial":
        return "status-partial"
    if s in ("restricted", "restrict", "restriction"):
        return "status-restrict"
    if s == "open":
        return "status-open"
    return ""

def infer_status_from_text(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"\bclosed\b", t):
        return "closed"
    if re.search(r"\bpartial\b", t):
        return "partial"
    if "restrict" in t:
        return "restricted"
    if re.search(r"\bopen\b", t):
        return "open"
    return ""

def capitalize_first_alpha(s: str) -> str:
    """
    Capitalize the first alphabetic character in the string (keeps leading punctuation/whitespace).
    """
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
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"

def render_card(name: str, status: str, bullets: list[str], *,
                show_placeholder: bool = True,
                max_bullets: int = 3,
                max_bullet_len: int = 180):
    """
    Bigger name + status, small notes.
    """
    name = (name or "").strip()
    status = (status or "").strip().lower()

    s_cls = status_class(status)
    status_html = ""
    if status:
        status_html = f'<div class="statusline {s_cls}">{status.upper()}</div>'

    bullets = [clamp_text(b, max_bullet_len) for b in (bullets or []) if b and b.strip()]
    bullets = bullets[:max_bullets]

    if bullets:
        notes_html = "<br/>".join([f"• {b}" for b in bullets])
        notes_html = f'<div class="notes">{notes_html}</div>'
    else:
        if show_placeholder:
            notes_html = '<div class="notes">• —</div>'
        else:
            notes_html = ""

    st.markdown(
        f"""
        <div class="card">
          <div class="name">{name}</div>
          {status_html}
          {notes_html}
        </div>
        """,
        unsafe_allow_html=True
    )

def split_blocks(raw: str):
    parts = [p.strip() for p in raw.split("------------------")]
    parts = [p for p in parts if p]
    borders_block = parts[0] if len(parts) >= 1 else ""
    airspace_block = parts[1] if len(parts) >= 2 else ""
    impacts_block = parts[2] if len(parts) >= 3 else ""
    return borders_block, airspace_block, impacts_block

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

        # compact bullets: max 3 sentences, trimmed later in render_card
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
            # fallback: show whole line as a "country" label
            items.append({"country": ln, "status": "", "notes": ""})
            continue

        country = m.group("country").strip()
        status = m.group("status").strip().lower()
        rest = (m.group("rest") or "").strip()

        # extra text after status becomes notes (e.g., "Saudi open and absorbing reroutes...")
        if rest:
            rest = rest.lstrip(" -–—:").strip()
            if rest:
                notes = (rest + ((" " + notes) if notes else "")).strip()

        # Capitalize first letter after ';' (i.e., first alphabetic char in notes)
        notes = capitalize_first_alpha(notes)

        # Drop pointless notes that equal the country name
        if notes.lower().strip(". ") == country.lower().strip(". "):
            notes = ""

        items.append({"country": country, "status": status, "notes": notes})

    if not items:
        items.append({"country": "Airspace (no entries)", "status": "", "notes": ""})

    return items

# ----------------------------
# Parsing: Impacts (exact headers: Country:)
# ----------------------------
def parse_impacts(block: str):
    lines = [ln.rstrip() for ln in block.split("\n")]

    cleaned = []
    for ln in lines:
        if re.match(r"(?i)^\s*Confirmed impacts", ln.strip()):
            continue
        cleaned.append(ln)
    lines = cleaned

    items = []
    current_country = None
    buf = []

    def flush():
        nonlocal current_country, buf, items
        if current_country is None:
            buf = []
            return
        text = " ".join([b.strip() for b in buf if b.strip()]).strip()

        bullets = []
        if text:
            parts = re.split(r"(?<=[.!?])\s+", text)
            for p in parts:
                p = p.strip()
                if p:
                    bullets.append(p)
                if len(bullets) >= 2:
                    break

        items.append({"country": current_country, "bullets": bullets})
        current_country, buf = None, []

    for ln in lines:
        s = ln.strip()
        if not s:
            continue

        m = re.match(r"^([A-Za-z][A-Za-z\s\-/]+):\s*(.*)$", s)
        if m:
            flush()
            current_country = m.group(1).strip()
            remainder = m.group(2).strip()
            if remainder:
                buf.append(remainder)
        else:
            if current_country is not None:
                buf.append(s)

    flush()

    if not items:
        items.append({"country": "Impacts (no entries)", "bullets": []})

    return items

# ----------------------------
# Load + parse
# ----------------------------
raw = normalize(load_update("update.txt"))
borders_block, airspace_block, impacts_block = split_blocks(raw)

borders = parse_borders(borders_block)
airspace = parse_airspace(airspace_block)
impacts = parse_impacts(impacts_block)

# Optional: detect "as of Month Day" anywhere
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
      <div class="meta"><b>AS OF:</b> {as_of or "—"} </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ----------------------------
# Single-screen packing strategy:
# - Borders remain 1 column (usually longer narrative)
# - Airspace split into 2 subcolumns to avoid vertical scroll
# - Strike impacts split into 2 subcolumns to avoid vertical scroll
# - Bullets capped + trimmed
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
            max_bullet_len=210
        )

with c2:
    st.markdown('<div class="section-title">AIRSPACE</div>', unsafe_allow_html=True)

    # split airspace into two subcolumns for height reduction
    a_left, a_right = st.columns(2, gap="small")
    for idx, a in enumerate(airspace):
        bullets = [a["notes"]] if a.get("notes") else []
        target = a_left if idx % 2 == 0 else a_right
        with target:
            render_card(
                a["country"],
                a["status"],
                bullets,
                show_placeholder=False,   # <-- no "• —" in airspace
                max_bullets=1,            # keep it tight
                max_bullet_len=140
            )

with c3:
    st.markdown('<div class="section-title">CONFIRMED STRIKE IMPACTS</div>', unsafe_allow_html=True)

    # split impacts into two subcolumns for height reduction
    i_left, i_right = st.columns(2, gap="small")
    for idx, i in enumerate(impacts):
        target = i_left if idx % 2 == 0 else i_right
        with target:
            render_card(
                i["country"],
                "",
                i["bullets"],
                show_placeholder=True,  # show "—" for empty entries like "Oman:"
                max_bullets=2,
                max_bullet_len=140
            )
