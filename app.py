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

  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
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

def render_card(name: str, status: str, bullets: list[str]):
    s_cls = status_class(status)
    status_html = f'<span class="{s_cls}">{status.upper()}</span>' if status else ""
    bullet_html = "<br/>".join([f"• {b}" for b in bullets if b.strip()]) if bullets else "• —"
    st.markdown(
        f"""
        <div class="card">
          <div class="row">
            <div class="name">{name}</div>
          </div>
          <div class="lines">{status_html}<br/>{bullet_html}</div>
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
    # Be resilient if someone accidentally adds extra separators
    parts = [p for p in parts if p]

    borders_block = parts[0] if len(parts) >= 1 else ""
    airspace_block = ""
    impacts_block = ""

    if len(parts) >= 2:
        airspace_block = parts[1]
    if len(parts) >= 3:
        impacts_block = parts[2]

    return borders_block, airspace_block, impacts_block

# ----------------------------
# Parsing: Borders (exact headers)
# ----------------------------
def parse_borders(block: str):
    """
    Uses exact border headers.
    Everything after a header until the next header is its body.
    """
    # Remove the intro line if present
    lines = [ln.strip() for ln in block.split("\n")]

    # Build a single string with line breaks preserved
    text = "\n".join(lines).strip()

    # Find positions of each header in the text (as whole lines)
    # We'll search line-by-line for exact matches to avoid false positives.
    idxs = []
    for i, ln in enumerate(lines):
        if ln in BORDER_HEADERS:
            idxs.append((i, ln))

    items = []
    for n, (start_i, header) in enumerate(idxs):
        end_i = idxs[n + 1][0] if n + 1 < len(idxs) else len(lines)
        body_lines = [l.strip() for l in lines[start_i + 1:end_i] if l.strip()]

        # Condense body: keep as up to 4 bullets:
        # - split by blank lines AND by sentence boundaries lightly
        body_text = " ".join(body_lines).strip()

        bullets = []
        if body_text:
            # Keep operator-readable chunks: split by sentence endings, cap at 4
            parts = re.split(r"(?<=[.!?])\s+", body_text)
            for p in parts:
                p = p.strip()
                if p:
                    bullets.append(p)
                if len(bullets) >= 4:
                    break

        # Infer a simple status from the body (Open/Closed/Restricted/Partial)
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

    # If headers are missing (bad paste), show a minimal fallback card
    if not items:
        items.append({
            "name": "Borders (format issue)",
            "status": "",
            "bullets": ["Could not detect border headers. Ensure exact header lines are used."]
        })

    return items

# ----------------------------
# Parsing: Airspace (Country status; optional notes)
# ----------------------------
def parse_airspace(block: str):
    """
    Expected lines after the AIRSPACE title:
      Israel closed
      UAE partial closure
      Jordan open; flight availability impacted...
    Rules:
      - Country is first token/group until status word.
      - Status is one of: open, closed, partial
      - Optional notes after ';' (or after status if extra text exists).
    """
    lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
    # Drop "AIRSPACE" title line if present
    if lines and lines[0].strip().upper() == "AIRSPACE":
        lines = lines[1:]

    items = []
    status_words = ["open", "closed", "partial"]

    for ln in lines:
        # Split notes if present
        main, sep, tail = ln.partition(";")
        main = main.strip()
        notes = tail.strip() if sep else ""

        # Extract "country" + status from main
        # Examples:
        #   "Israel closed"
        #   "UAE partial closure"  -> status=partial, leftover="closure" should go into notes
        m = re.match(r"^(?P<country>.+?)\s+(?P<status>open|closed|partial)\b(?P<rest>.*)$", main, flags=re.I)
        if not m:
            # If badly formed, show whole line as a note
            items.append({"country": ln, "status": "", "notes": ""})
            continue

        country = m.group("country").strip()
        status = m.group("status").strip().lower()
        rest = (m.group("rest") or "").strip()

        # If there's extra text after status (like "closure" or "and absorbing..."), treat as notes
        if rest:
            rest = rest.lstrip(" -–—:").strip()
            if rest:
                notes = (rest + ((" " + notes) if notes else "")).strip()

        # Remove pointless notes that equal the country name
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
    """
    Country headers are EXACTLY the country name before ":".
    Text can span multiple lines until the next "X:" header or end.
    """
    lines = [ln.rstrip() for ln in block.split("\n")]

    # Remove the intro line if present
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
        # If empty (e.g., "Oman:"), still show a placeholder dash
        items.append({"country": current_country, "bullets": bullets if bullets else ["—"]})
        current_country, buf = None, []

    for ln in lines:
        s = ln.strip()
        if not s:
            continue

        m = re.match(r"^([A-Za-z][A-Za-z\s\-/]+):\s*(.*)$", s)
        if m:
            # new header
            flush()
            current_country = m.group(1).strip()
            remainder = m.group(2).strip()
            if remainder:
                buf.append(remainder)
        else:
            # continuation line
            if current_country is not None:
                buf.append(s)

    flush()

    if not items:
        items.append({"country": "Impacts (no entries)", "bullets": ["—"]})

    return items

# ----------------------------
# Load + parse
# ----------------------------
raw = normalize(load_update("update.txt"))
borders_block, airspace_block, impacts_block = split_blocks(raw)

borders = parse_borders(borders_block)
airspace = parse_airspace(airspace_block)
impacts = parse_impacts(impacts_block)

# Try to detect an "as of Month Day" anywhere in the text (optional)
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
        render_card(b["name"], b["status"], b["bullets"])

with c2:
    st.markdown('<div class="section-title">AIRSPACE</div>', unsafe_allow_html=True)
    for a in airspace:
        bullets = []
        if a["notes"]:
            bullets = [a["notes"]]
        else:
            bullets = ["—"]
        render_card(a["country"], a["status"], bullets)

with c3:
    st.markdown('<div class="section-title">CONFIRMED IMPACTS</div>', unsafe_allow_html=True)
    for i in impacts:
        render_card(i["country"], "", i["bullets"])
