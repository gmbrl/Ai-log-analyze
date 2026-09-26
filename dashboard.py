import os
import re
from datetime import datetime

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# --- Page Setup ---
st.set_page_config(
    page_title="OpsPilot | Incident Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- Fallback Models (if API is not yet provided) ---
FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "deepseek-r1-distill-llama-70b",
]

# --- Preset Scenarios ---
PRESET_SAMPLES = {
    "PostgreSQL Pool Exhaustion": (
        "2025-02-18 10:00:01 [ERROR] [auth-service] org.postgresql.util.PSQLException: FATAL: remaining connection slots are reserved for non-replication superuser connections\n"
        "2025-02-18 10:00:03 [FATAL] [api-gateway] 500 Internal Server Error - Downstream auth-service unreachable\n"
        "2025-02-18 10:00:05 [WARN]  [billing-worker] HikariCP - Connection pool 'auth-pool' is full (total=50, active=50, idle=0, waiting=128)\n"
        "2025-02-18 10:00:12 [ERROR] [api-gateway] CircuitBreaker 'auth-service-cb' state changed from CLOSED to OPEN"
    ),
    "Kubernetes OOMKilled": (
        "2025-02-18 14:22:10 [INFO]  [k8s-node-04] Memory usage of pod 'recommendation-engine' reached 98.4% of limit (4096Mi)\n"
        "2025-02-18 14:22:15 [FATAL] [kernel] Out of memory: Kill process 28419 (python3) score 950\n"
        "2025-02-18 14:22:16 [WARN]  [kubelet] Pod terminated with exit code 137 (OOMKilled)\n"
        "2025-02-18 14:22:18 [ERROR] [ingress-nginx] 502 Bad Gateway while connecting upstream"
    ),
    "AWS S3 Access Denied": (
        "2025-02-18 08:14:02 [INFO]  [data-pipeline] Starting daily ETL job batch_id=89231\n"
        "2025-02-18 08:14:05 [ERROR] [data-pipeline] ClientError: AccessDenied when calling PutObject\n"
        "2025-02-18 08:14:06 [FATAL] [data-pipeline] Failed to push processed dataset to S3\n"
        "2025-02-18 08:14:10 [ERROR] [airflow-scheduler] Task instance failed in WorkerNode"
    ),
}

SYSTEM_PROMPT = """You are a Principal SRE and Incident Commander. Analyze the logs and return concise GitHub-flavored Markdown with exactly these sections:
### 1. Executive Summary & Severity
- **Severity**: [P1 - Critical / P2 - High / P3 - Moderate / P4 - Low]
- **Impact**: [Brief business/service impact statement]
### 2. Root Cause Analysis
- **Failure Mechanism**: [Detailed technical explanation of failure]
- **Trigger Event**: [Initial log event that sparked cascading failure]
### 3. Immediate Mitigation Runbook
Give ordered actionable steps with safe commands/queries where useful.
### 4. Long-term Prevention & Monitoring
Include concrete alerts, SLOs, dashboards, and architecture fixes.
Clearly separate observed evidence from assumptions. Never invent facts not present in the logs."""


# --- Dynamic Model Discovery ---
@st.cache_data(ttl=600, show_spinner=False)
def fetch_available_models(api_key: str):
    """Fetches the live list of models your Groq API key has access to."""
    if not api_key:
        return FALLBACK_MODELS
    try:
        res = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout=8,
        )
        if res.status_code == 200:
            data = res.json().get("data", [])
            # Filter out non-chat models (audio, embeddings, guardrails)
            chat_models = [
                m["id"] for m in data
                if not any(k in m["id"] for k in ["whisper", "guard", "embed", "tts", "moderation"])
            ]
            if chat_models:
                chat_models.sort()
                return chat_models
    except Exception:
        pass
    return FALLBACK_MODELS


# --- Groq Log Analysis ---
def analyze_logs(api_key: str, logs: str, model: str, temperature: float):
    cleaned_key = api_key.strip() if api_key else ""
    if not cleaned_key:
        return "❌ **Configuration Error:** Please add your Groq API key in the sidebar or `.env`."

    payload = {
        "model": model.strip(),
        "temperature": temperature,
        "max_tokens": 1600,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this log stream:\n```text\n{logs}\n```"},
        ],
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {cleaned_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )

        data = response.json()
        if response.status_code != 200 or "error" in data:
            error_message = data.get("error", {}).get("message", response.text)
            return f"❌ **Groq API Error ({response.status_code}):** {error_message}"

        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as exc:
        return f"❌ **Network Error:** `{exc}`"
    except (KeyError, IndexError, ValueError) as exc:
        return f"❌ **Response Parsing Error:** `{exc}`"


def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
    :root { --ink:#e8eef7; --muted:#8b9ab0; --panel:#111b2c; --line:#213149; --cyan:#31d4c6; --purple:#9b8cff; --red:#ff6b7a; --amber:#f5bd55; }
    .stApp { background: #09111f; color: var(--ink); }
    [data-testid="stSidebar"] { background:#0b1526; border-right:1px solid var(--line); }
    [data-testid="stSidebar"] > div:first-child { padding: 1.5rem 1.15rem; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
    h1,h2,h3,h4 { font-family:'Space Grotesk',sans-serif !important; }
    .brand { display:flex; align-items:center; gap:11px; margin-bottom:2.2rem; }
    .brand-mark { width:34px; height:34px; display:grid; place-items:center; border-radius:10px; background:linear-gradient(135deg,var(--cyan),var(--purple)); color:#06111c; font-weight:800; font-size:1.1rem; }
    .brand-title { font:700 1.15rem 'Space Grotesk'; letter-spacing:.02em; }
    .brand-sub { color:var(--muted); font-size:.72rem; margin-top:2px; }
    .topline { display:flex; justify-content:space-between; align-items:start; margin:8px 0 26px; }
    .eyebrow { color:var(--cyan); text-transform:uppercase; letter-spacing:.16em; font-size:.7rem; font-weight:700; }
    .page-title { font:700 2rem 'Space Grotesk'; margin:5px 0; }
    .page-subtitle { color:var(--muted); font-size:.9rem; }
    .status { border:1px solid #24594f; background:#102c2d; color:#6ee7bd; padding:8px 12px; border-radius:999px; font-size:.75rem; font-weight:600; }
    .panel { background:linear-gradient(145deg,#111d30,#0e1828); border:1px solid var(--line); border-radius:16px; padding:20px; margin-bottom:18px; box-shadow:0 10px 35px rgba(2, 7, 17, 0.2); }
    .panel-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; }
    .panel-title { font:600 1rem 'Space Grotesk'; }
    .panel-note { color:var(--muted); font-size:.75rem; }
    .metric { background:#0d1727; border:1px solid var(--line); border-radius:12px; padding:12px 16px; text-align:center; }
    .metric-label { color:var(--muted); font-size:.7rem; text-transform:uppercase; letter-spacing:.1em; }
    .metric-value { font:700 1.45rem 'Space Grotesk'; margin-top:4px; }
    .metric-accent { color:var(--cyan); }
    .empty { min-height:420px; display:grid; place-items:center; text-align:center; color:var(--muted); }
    .empty-icon { font-size:2.8rem; color:var(--cyan); margin-bottom:10px; }
    code, pre, textarea { font-family:'JetBrains Mono',monospace !important; font-size:0.85rem !important; }
    .stButton > button, .stDownloadButton > button { border-radius:9px; border:1px solid #2b405a; background:#15243a; color:var(--ink); font-weight:600; }
    .stButton > button:hover { border-color:var(--cyan); color:var(--cyan); }
    div[data-testid="stTextArea"] textarea { background:#0a1423; border-color:#263b55; border-radius:10px; }
    .hint { color:var(--muted); font-size:.75rem; line-height:1.5; }
    </style>
    """, unsafe_allow_html=True)


def metric_card(label, value, accent=""):
    return f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value {accent}">{value}</div></div>'


# --- State Initialization ---
if "logs" not in st.session_state:
    st.session_state.logs = ""
if "report" not in st.session_state:
    st.session_state.report = ""

inject_css()

# --- Sidebar ---
with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">◈</div><div><div class="brand-title">OpsPilot</div><div class="brand-sub">Incident intelligence console</div></div></div>', unsafe_allow_html=True)
    st.markdown("#### Analysis engine")
    
    api_key = st.text_input(
        "Groq API key", 
        value=DEFAULT_API_KEY, 
        type="password", 
        help="Loaded from GROQ_API_KEY in .env by default."
    )

    # Automatically fetch real models available to this key
    available_models = fetch_available_models(api_key)
    
    # Pick a sensible default from whatever is available
    default_idx = 0
    if "llama-3.3-70b-versatile" in available_models:
        default_idx = available_models.index("llama-3.3-70b-versatile")
    elif "llama3-70b-8192" in available_models:
        default_idx = available_models.index("llama3-70b-8192")

    model = st.selectbox("Model", options=available_models, index=default_idx)
    temperature = st.slider("Strictness / Temperature", 0.0, 1.0, 0.2, 0.05)
    
    st.divider()
    st.markdown("#### Quick-start scenarios")
    for name, sample in PRESET_SAMPLES.items():
        if st.button(name, use_container_width=True):
            st.session_state.logs = sample
            st.session_state.report = ""
            
    st.divider()
    st.markdown('<div class="hint">🔒 Tip: Sanitize tokens, credentials, and PII before submitting logs to external LLM providers.</div>', unsafe_allow_html=True)

# --- Main Columns ---
left, right = st.columns([1.05, 1.25], gap="large")

with left:
    st.markdown('<div class="topline"><div><div class="eyebrow">Operations / live triage</div><div class="page-title">Incident workspace</div><div class="page-subtitle">Turn raw telemetry dumps into structured mitigation runbooks.</div></div><div class="status">● Console ready</div></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">Telemetry intake</div><div class="panel-note">Paste or upload log stream</div></div>', unsafe_allow_html=True)
    
    uploaded = st.file_uploader("Upload log file", type=["log", "txt", "json"], label_visibility="collapsed")
    if uploaded:
        st.session_state.logs = uploaded.read().decode("utf-8", errors="ignore")

    logs = st.text_area(
        label="Raw logs",
        value=st.session_state.logs,
        height=320,
        placeholder="Paste application logs, syslog lines, stack traces, or container outputs here...",
        label_visibility="collapsed"
    )
    st.session_state.logs = logs
    st.markdown('</div>', unsafe_allow_html=True)

    # Real-time Metrics
    if logs.strip():
        lines = len(logs.splitlines())
        errors = len(re.findall(r'(?i)\b(error|fatal|exception|panic|failed|denied)\b', logs))
        warns = len(re.findall(r'(?i)\b(warn|warning)\b', logs))
    else:
        lines = errors = warns = 0

    m1, m2, m3 = st.columns(3)
    m1.markdown(metric_card("Log Lines", lines, "metric-accent"), unsafe_allow_html=True)
    m2.markdown(metric_card("Errors / Fatals", errors, "style='color:#ff6b7a;'"), unsafe_allow_html=True)
    m3.markdown(metric_card("Warnings", warns, "style='color:#f5bd55;'"), unsafe_allow_html=True)

    st.write("")
    run_col, clear_col = st.columns([3, 1])
    with run_col:
        analyze = st.button("🚀 Run incident analysis", type="primary", use_container_width=True)
    with clear_col:
        if st.button("🧹 Clear", use_container_width=True):
            st.session_state.logs = ""
            st.session_state.report = ""
            st.rerun()

with right:
    st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">Diagnostic report</div><div class="panel-note">AI-assisted · root cause localized</div></div>', unsafe_allow_html=True)
    
    if analyze:
        if not logs.strip():
            st.warning("⚠️ Log stream is empty. Provide log content or select a preset scenario.")
        elif not api_key:
            st.error("🔑 Groq API key is missing. Set it in `.env` or input it in the sidebar.")
        else:
            with st.spinner("🤖 Correlating log events and generating runbook..."):
                st.session_state.report = analyze_logs(
                    api_key=api_key,
                    logs=logs,
                    model=model,
                    temperature=temperature,
                )

    if st.session_state.report:
        st.markdown(st.session_state.report)
        st.markdown("---")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="💾 Download Incident Runbook (.md)",
            data=st.session_state.report,
            file_name=f"opspilot_incident_{timestamp}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    else:
        st.markdown("""
        <div class="empty">
            <div>
                <div class="empty-icon">◈</div>
                <div style="font-weight:600; margin-bottom:4px; font-size:1.05rem;">No active diagnostic run</div>
                <div style="font-size:0.82rem;">Select a preset scenario or ingest logs on the left to generate an incident diagnosis.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)