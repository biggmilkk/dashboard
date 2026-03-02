import re
from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="Ops Infoboard",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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

def load_update(path="update.txt") -> str:
    p = Path(path)
    if not p.exists():
        st.error(f"Missing {path}. Create it and paste your bulletin text.")
        st.stop()
    return p.read_text(encoding="utf-8", errors="ignore")

def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text

def split_sections(raw: str):
    airspace_match = re.search(r"(?im)^\s*AIRSPACE\s*$", raw)
    impacts_match = re.search(r"(?im)^\s*Confirmed impacts", raw)

    borders_block = raw
    airspace_block = ""
    impacts_block = ""

    if airspace_match:
        borders_block = raw[:airspace_match.start()].strip()
        rest = raw[airspace_match.end():].strip()
        impacts_match2 = re.search(r"(?im)^\s*Confirmed impacts", rest)
        if impacts_match2:
            airspace_block = rest[:impacts_match2.start()].strip()
            impacts_block = rest[impacts_match2.start():].strip()
        else:
            airspace_block = rest

    if (not airspace_match) and impacts_match:
        borders_block = raw[:impacts_match.start()].strip()
        impacts_block = raw[impacts_match.start():].strip()

    return borders_block, airspace_block, impacts_block

def infer_status(text: str) -> str:
    t = (text or "").lower()
    if "closed" in t or "closes its airspace" in t:
        return "CLOSED"
    if "partial" in t:
        return "PARTIAL"
    if "restrict" in t:
        return "RESTRICTED"
    if re.search(r"\bopen\b", t):
        return "OPEN"
    return ""

def status_class(status: str) -> str:
    s = (status or "").upper()
    if s == "CLOSED": return "status-closed"
    if s == "PARTIAL": return "status-partial"
    if s == "RESTRICTED": return "status-restrict"
    if s == "OPEN": return "status-open"
    return ""

def render_card(name, status, bullets):
    s_cls = status_class(status)
    status_html = f'<span class="{s_cls}">{status}</span>' if status else ""
    bullet_html = "<br/>".join([f"• {b}" for b in bullets]) if bullets else "• —"
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

def parse_borders(block: str):
    lines = [ln.strip() for ln in block.split("\n")]
    items = []
    current = None
    buf = []

    def flush():
        nonlocal current, buf
        if current:
            text = " ".join([b for b in buf if b]).strip()
            status = infer_status(text)
            bullets = []
            if text:
                parts = re.split(r"(?<=[.!?])\s+", text)
                for p in parts:
                    p = p.strip()
                    if p:
                        bullets.append(p)
                    if len(bullets) >= 3:
                        break
            items.append({"name": current, "status": status, "bullets": bullets})
        current, buf = None, []

    heading_re = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/()\-\s]{2,}$")

    for ln in lines:
        if not ln:
            continue
        if ln.lower().startswith("land border status"):
            continue
        if (not ln.endswith(".")) and heading_re.match(ln) and len(ln) <= 80:
            flush()
            current = ln
            continue
        if current:
            buf.append(ln)

    flush()
    return items

def parse_airspace(block: str):
    items = []
    for ln in [l.strip() for l in block.split("\n") if l.strip()]:
        region = ln
        m = re.match(r"^([A-Za-z][A-Za-z\s\-]+?)\s+(closes|announces|airspace)\b", ln, flags=re.I)
        if m:
            region = m.group(1).strip()

        status = infer_status(ln)

        # note cleanup
        note = ln.strip()

        # If it's exactly "X closes its airspace." → note should be empty
        note = re.sub(r"(?i)^\s*"+re.escape(region)+r"\s+closes its airspace\.?\s*$", "", note).strip()

        # General cleanup (keeps useful extras like timings/NOTAM details)
        note = re.sub(r"(?i)\bcloses its airspace\.?\s*", "", note).strip()

        # If note collapses to just the region name, drop it
        if note.lower().strip(". ") == region.lower().strip(". "):
            note = ""

        items.append({"region": region, "status": status, "note": note})
    return items

def parse_impacts(block: str):
    block = re.sub(r"(?im)^\s*Confirmed impacts.*\n?", "", block).strip()
    items = []
    for ln in [l.strip() for l in block.split("\n") if l.strip()]:
        m = re.match(r"^([A-Za-z][A-Za-z\s\-/]+?):\s*(.*)$", ln)
        if m:
            country = m.group(1).strip()
            text = m.group(2).strip()
            items.append({"country": country, "text": text})
        else:
            if items:
                items[-1]["text"] = (items[-1]["text"] + " " + ln).strip()

    out = []
    for it in items:
        bullets = []
        parts = re.split(r"(?<=[.!?])\s+", it["text"])
        for p in parts:
            p = p.strip()
            if p:
                bullets.append(p)
            if len(bullets) >= 2:
                break
        out.append({"country": it["country"], "bullets": bullets})
    return out

raw = normalize(load_update("update.txt"))
borders_block, airspace_block, impacts_block = split_sections(raw)

borders = parse_borders(borders_block)
airspace = parse_airspace(airspace_block) if airspace_block else []
impacts = parse_impacts(impacts_block) if impacts_block else []

# Header: try to detect "as of Month Day"
as_of = ""
m_asof = re.search(r"(?i)\bas of\s+([A-Za-z]+\s+\d{1,2})", raw)
if m_asof:
    as_of = m_asof.group(1)

st.markdown(
    f"""
    <div class="topbar">
      <div class="title">Regional Disruptions — Quick View</div>
      <div class="meta"><b>AS OF:</b> {as_of or "—"} &nbsp;&nbsp;|&nbsp;&nbsp; <b>BACKEND:</b> update.txt</div>
    </div>
    """,
    unsafe_allow_html=True
)

c1, c2, c3 = st.columns([1.25, 1.0, 1.0], gap="large")

with c1:
    st.markdown('<div class="section-title">LAND BORDERS</div>', unsafe_allow_html=True)
    for b in borders:
        render_card(b["name"], b["status"], b["bullets"])

with c2:
    st.markdown('<div class="section-title">AIRSPACE</div>', unsafe_allow_html=True)
    for a in airspace:
        # show 1 concise bullet per line item
        render_card(a["region"], a["status"], [a["note"]] if a["note"] else [])

with c3:
    st.markdown('<div class="section-title">CONFIRMED IMPACTS</div>', unsafe_allow_html=True)
    for i in impacts:
        render_card(i["country"], "", i["bullets"])
