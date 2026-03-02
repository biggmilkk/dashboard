import re
from pathlib import Path
import streamlit as st

# ----------------------------
# Page config (no sidebar, wall-screen friendly)
# ----------------------------
st.set_page_config(
    page_title="Ops Infoboard",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----------------------------
# Low-glare dark styling
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
    padding: 14px 16px;
    margin-bottom: 14px;
  }
  .title { font-size: 26px; font-weight: 900; margin: 0; line-height: 1.1; }
  .meta  { margin-top: 6px; font-size: 13px; color: rgba(230,237,243,0.75); }

  .section-title { font-size: 18px; font-weight: 900; margin: 8px 0 10px 0; }

  .card {
    background: #0f1620;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 12px 12px 10px 12px;
    margin-bottom: 10px;
  }
  .row { display:flex; gap:10px; align-items:center; justify-content:space-between; }
  .name { font-size: 15px; font-weight: 900; margin: 0; }
  .lines { margin-top: 6px; font-size: 13px; color: rgba(230,237,243,0.92); line-height: 1.35; }

  .status-open      { color: rgba(82,196,26,1.0); font-weight: 900; }
  .status-closed    { color: rgba(255,77,79,1.0); font-weight: 900; }
  .status-partial   { color: rgba(255,169,64,1.0); font-weight: 900; }
  .status-restrict  { color: rgba(250,219,20,1.0); font-weight: 900; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Update.txt format rules (your declared "truth")
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

def render_card(name: str, status: str, bullets: list[str], show_placeholder: bool = True):
    """
    show_placeholder=True  -> if bullets empty, show '• —'
    show_placeholder=False -> if bullets empty, show nothing after status
    """
    s_cls = status_class(status)
    status_html = f'<span class="{s_cls}">{status.upper()}</span>' if status else ""

    bullets = [b.strip() for b in (bullets or []) if b and b.strip()]
    if bullets:
        bullet_html = "<br/>".join([f"• {b}" for b in bullets])
        body_html = f"{status_html}<br/>{bullet_html}" if status_html else bullet_html
    else:
        if show_placeholder:
            body_html = f"{status_html}<br/>• —" if status_html else "• —"
        else:
            body_html = f"{status_html}" if status_html else ""

    st.markdown(
        f"""
        <div class="card">
          <div class="row">
            <div class="name">{name}</div>
          </div>
          <div class="lines">{body_html}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def split_blocks(raw: str):
    """
    Expected structure:
      [Borders section ...]
      ------------------
      AIRSPACE
      [Airspace lines ...]
      ------------------
      [Impacts section ...]
    """
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
    idxs = []
    for i, ln in enumerate(lines):
        if ln in BORDER_HEADERS:
            idxs.append((i, ln))

    items = []
    for n, (start_i, header) in enumerate(idxs):
        end_i = idxs[n + 1][0] if n + 1 < len(idxs) else len(lines)
        body_lines = [l.strip() for l in lines[start_i + 1:end_i] if l.strip()]
        body_text = " ".join(body_lines).strip()

        bullets = []
        if body_text:
            parts = re.split(r"(?<=[.!?])\s+", body_text)
            for p in parts:
                p = p.strip()
                if p:
                    bullets.append(p)
                if len(bullets) >= 4:
                    break

        # infer a simple status from the body
        status = ""
        t = body_text.lower()
        if re.search(r"\bclosed\b", t):
            status = "closed"
        elif re.search(r"\bpartial\b", t):
            status = "partial"
        elif "restrict" in t:
            status = "restricted"
        elif re.search(r"\bopen\b", t):
            status = "open"

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

        # extra text after status becomes notes (e.g., "Saudi open and absorbing reroutes...")
        if rest:
            rest = rest.lstrip(" -–—:").strip()
            if rest:
                notes = (rest + ((" " + notes) if notes else "")).strip()

        # drop pointless notes that equal the country
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
                if len(bullets) >= 3:
                    break
        items.append({"country": current_country, "bullets": bullets if bullets else []})
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

# Optional: detect "as of Month Day"
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
      <div class="title">Regional Disruptions — Quick View</div>
      <div class="meta"><b>AS OF:</b> {as_of or "—"} &nbsp;&nbsp;|&nbsp;&nbsp; <b>BACKEND:</b> update.txt</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ----------------------------
# Main 3-column board
# ----------------------------
c1, c2, c3 = st.columns([1.25, 1.0, 1.0], gap="large")

with c1:
    st.markdown('<div class="section-title">LAND BORDERS</div>', unsafe_allow_html=True)
    for b in borders:
        render_card(b["name"], b["status"], b["bullets"], show_placeholder=True)

with c2:
    st.markdown('<div class="section-title">AIRSPACE</div>', unsafe_allow_html=True)
    for a in airspace:
        # IMPORTANT: no placeholder bullets in airspace
        bullets = [a["notes"]] if a.get("notes") else []
        render_card(a["country"], a["status"], bullets, show_placeholder=False)

with c3:
    st.markdown('<div class="section-title">CONFIRMED IMPACTS</div>', unsafe_allow_html=True)
    for i in impacts:
        # If a country header exists but has no details (e.g., "Oman:"), show a placeholder dash
        render_card(i["country"], "", i["bullets"], show_placeholder=True)
