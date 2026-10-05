import hashlib
import html
import io
import json
import os
import re
import textwrap
import sys
import time
import base64
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from PIL import Image

# Groq Client
try:
    from groq import Groq
except ImportError:
    Groq = None

# PDF and OCR Parsers
try:
    import pypdf
except ImportError:
    pypdf = None
try:
    import pytesseract
except ImportError:
    pytesseract = None
try:
    import pdf2image
except ImportError:
    pdf2image = None

# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="ClarityLab AI | Biomarker Dashboard",
    page_icon=":material/biotech:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def render_html(html_str: str) -> None:
    st.html(textwrap.dedent(html_str).strip())

def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))

def svg_uri(svg: str) -> str:
    """Inline SVG is stripped by st.html, so animated graphics ship as data-URI images."""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("utf-8")

# ---------------------------------------------------------
# Animated heartbeat line (data-URI SVG, animates inside <img>/background)
# ---------------------------------------------------------
_ECG_PATH = ("M0 38 H300 L316 32 L330 38 H400 L414 42 L432 6 L452 56 L468 28 L480 38 "
             "H760 L776 32 L790 38 H860 L874 42 L892 6 L912 56 L928 28 L940 38 H1200")
ECG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 60" width="1200" height="60">
<style>
.l{{fill:none;stroke-linecap:round;stroke-linejoin:round}}
.b{{stroke:#b6ff3c;stroke-opacity:.16;stroke-width:1.6}}
.c{{stroke:url(#g);stroke-width:3.4;stroke-dasharray:170 830;animation:m 4s linear infinite;filter:url(#f)}}
@keyframes m{{from{{stroke-dashoffset:170}}to{{stroke-dashoffset:-830}}}}
</style>
<defs><filter id="f" x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="#1ff2a0" stop-opacity="0"/><stop offset=".35" stop-color="#b6ff3c"/>
<stop offset=".7" stop-color="#ffd426"/><stop offset="1" stop-color="#ff3b72"/></linearGradient></defs>
<path class="l b" d="{_ECG_PATH}"/>
<path class="l c" pathLength="1000" d="{_ECG_PATH}"/>
</svg>"""
ECG_URI = svg_uri(ECG_SVG)

# ---------------------------------------------------------
# Theme: "Aurora HUD" - futuristic glass UI in lime / mint / sun-yellow
# with ember, flare-pink and violet accents.
# NOTE: this block is sanitised by Streamlit, so it must never contain a
# less-than sign followed by a letter (even inside @property syntax strings).
# ---------------------------------------------------------
THEME_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@300;400;500;600;700;800&family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700;800&family=Noto+Sans+Devanagari:wght@400;500;600;700&family=Noto+Sans+Gujarati:wght@400;500;600;700&display=swap');

/* ============================================================
   TOKENS
   ============================================================ */
@property --ang { syntax: '\3C angle\3E';   inherits: false; initial-value: 0deg; }
@property --n   { syntax: '\3C integer\3E'; inherits: false; initial-value: 0; }
@property --pct { syntax: '\3C number\3E';  inherits: false; initial-value: 0; }

:root {
    color-scheme: dark;
    --void: #03070a;
    --line: rgba(182, 255, 60, 0.16);
    --line-hi: rgba(182, 255, 60, 0.6);
    --text: #f2fff5;
    --muted: #8fa89c;

    --lime: #b6ff3c;
    --mint: #1ff2a0;
    --sun: #ffd426;
    --ember: #ff8a24;
    --flare: #ff3b72;
    --violet: #a176ff;

    --glow-lime: rgba(182, 255, 60, 0.45);
    --glow-mint: rgba(31, 242, 160, 0.45);
    --glow-sun: rgba(255, 212, 38, 0.45);
    --glow-flare: rgba(255, 59, 114, 0.5);
    --glow-violet: rgba(161, 118, 255, 0.45);

    --f-body: 'Outfit', 'Noto Sans Devanagari', 'Noto Sans Gujarati', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --f-display: 'Unbounded', 'Noto Sans Devanagari', 'Noto Sans Gujarati', 'Outfit', sans-serif;
    --f-mono: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;

    --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
    --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
    --ease-smooth: cubic-bezier(0.4, 0, 0.2, 1);

    --text-main: var(--text);
    --text-muted: var(--muted);
    --neon-amber: var(--sun);
    interpolate-size: allow-keywords;
}

/* ============================================================
   KEYFRAMES (implicit "to" frames keep hover transforms alive)
   ============================================================ */
@keyframes pageIn   { from { opacity: 0; transform: translateY(18px); } }
@keyframes cardIn   { from { opacity: 0; transform: translateY(34px) scale(0.95); } }
@keyframes panelIn  { from { opacity: 0; transform: translateY(22px); } }
@keyframes aurora   { 0% { transform: translate3d(0,0,0) rotate(0deg) scale(1); } 50% { transform: translate3d(3%,2%,0) rotate(4deg) scale(1.1); } 100% { transform: translate3d(-3%,-2%,0) rotate(-4deg) scale(1); } }
@keyframes gridDrift { to { background-position: 56px 56px, 56px 56px; } }
@keyframes spinAng  { to { --ang: 360deg; } }
@keyframes spinSlow { to { transform: rotate(360deg); } }
@keyframes ping     { 0% { transform: scale(0.8); opacity: 0.9; } 100% { transform: scale(2.6); opacity: 0; } }
@keyframes floatY   { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
@keyframes titleShift { to { background-position: 200% 0; } }
@keyframes laser    { 0% { top: -4%; opacity: 0; } 12% { opacity: 1; } 88% { opacity: 1; } 100% { top: 104%; opacity: 0; } }
@keyframes sheen    { from { background-position: -160% 0; } to { background-position: 160% 0; } }
@keyframes bracket  { 0%, 100% { opacity: 0.5; } 50% { opacity: 1; } }
@keyframes markerIn { from { left: 0%; opacity: 0; } }
@keyframes safeGrow { from { transform: scaleX(0); opacity: 0; } }
@keyframes ringFill { from { --pct: 0; } }
@keyframes countUp  { from { --n: 0; } }
@keyframes dqIn     { from { opacity: 0; transform: translateY(-12px); } }
@keyframes liIn     { from { opacity: 0; transform: translateX(-20px); } }
@keyframes pingSoft { 0% { transform: scale(1); opacity: 0.7; } 100% { transform: scale(2.1); opacity: 0; } }
@keyframes scanBar  { 0% { left: -40%; } 100% { left: 100%; } }
@keyframes pulseBar { 0%, 100% { opacity: 0.7; } 50% { opacity: 1; } }
@keyframes segIn    { from { opacity: 0; transform: scaleY(0.2); } }
@keyframes tipBob   { 0%, 100% { transform: translate(-50%, 0); } 50% { transform: translate(-50%, -3px); } }

/* ============================================================
   BASE + LIVING BACKGROUND
   ============================================================ */
html { scroll-behavior: smooth; }

html, body, .stApp,
.stApp :is(p, span, div, label, button, input, li, h1, h2, h3, h4, summary, small) {
    font-family: var(--f-body);
    -webkit-font-smoothing: antialiased;
}
.stApp [data-testid="stIconMaterial"], .stApp [class*="material-symbols"], .stApp .material-icons {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}

.stApp { background: var(--void) !important; color: var(--text); isolation: isolate; overflow-x: hidden; }
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stMainBlockContainer"] { background: transparent !important; }
[data-testid="stAppViewContainer"] { position: relative; z-index: 1; }
header[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stDecoration"], footer:not(.cl-footer) { display: none !important; }
[data-testid="stToolbar"] { color: var(--muted); }
.stElementContainer:has(.cl-fx) { display: none !important; }

.stApp::before {
    content: ""; position: fixed; inset: -30%; z-index: -2; pointer-events: none;
    background:
        radial-gradient(38% 38% at 16% 26%, rgba(182, 255, 60, 0.17), transparent 70%),
        radial-gradient(34% 34% at 84% 18%, rgba(255, 212, 38, 0.13), transparent 70%),
        radial-gradient(40% 40% at 74% 86%, rgba(31, 242, 160, 0.15), transparent 70%),
        radial-gradient(30% 30% at 8% 90%, rgba(255, 59, 114, 0.11), transparent 70%),
        radial-gradient(32% 32% at 50% 50%, rgba(161, 118, 255, 0.08), transparent 70%);
    animation: aurora 34s ease-in-out infinite alternate; will-change: transform;
}
.stApp::after {
    content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
    background-image:
        linear-gradient(rgba(182, 255, 60, 0.055) 1px, transparent 1px),
        linear-gradient(90deg, rgba(182, 255, 60, 0.055) 1px, transparent 1px);
    background-size: 56px 56px, 56px 56px;
    -webkit-mask-image: radial-gradient(ellipse 85% 75% at 50% 25%, #000 15%, transparent 78%);
    mask-image: radial-gradient(ellipse 85% 75% at 50% 25%, #000 15%, transparent 78%);
    animation: gridDrift 22s linear infinite;
}

.block-container, [data-testid="stMainBlockContainer"] { max-width: 1250px; padding-top: 3rem !important; padding-bottom: 5rem !important; }
[data-testid="stMainBlockContainer"] { animation: pageIn 1s var(--ease-out) backwards; }

::-webkit-scrollbar { width: 11px; height: 11px; }
::-webkit-scrollbar-track { background: var(--void); }
::-webkit-scrollbar-thumb { background: linear-gradient(var(--lime), var(--sun)); border-radius: 10px; border: 3px solid var(--void); }
::selection { background: var(--lime); color: #06130b; }

/* ============================================================
   TYPOGRAPHY
   ============================================================ */
.stApp .cl-title, .stApp .ob-title, .stApp .cl-h2, .stApp .cl-stat-value, .stApp .cl-ring-val,
.stApp .food-title, .stApp .dq-name, .stApp .metric-name, .stApp .metric-number { font-family: var(--f-display); }
.stApp .metric-raw, .stApp .metric-unit, .stApp .range-labels, .stApp .range-tip, .stApp .cl-eyebrow,
.stApp .pill, .stApp .cl-chip, .stApp .metric-cat, .stApp .ob-step, .stApp .dq-count,
.stApp .cl-sys-n, .stApp .dq-body li::before { font-family: var(--f-mono); }

.cl-title {
    margin: 0; padding: 0; font-size: 2.2rem; line-height: 1.12; font-weight: 700; letter-spacing: -0.03em;
    background: linear-gradient(100deg, #ffffff 0%, var(--lime) 28%, var(--sun) 52%, var(--mint) 78%, #ffffff 100%);
    background-size: 200% auto; -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
    animation: titleShift 9s linear infinite;
}
.cl-tagline { margin: 8px 0 0; font-size: 1.05rem; color: var(--muted); font-weight: 400; letter-spacing: 0.01em; }
.cl-h2 { margin: 0 0 10px; padding: 0; font-size: 1.75rem; line-height: 1.25; font-weight: 700; letter-spacing: -0.02em; color: var(--text); }
.cl-sub { margin: 0 0 22px; max-width: 70ch; font-size: 1.1rem; line-height: 1.7; color: var(--muted); }
.cl-eyebrow {
    display: inline-flex; align-items: center; gap: 8px; margin: 0 0 14px; padding: 5px 12px; border-radius: 8px;
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.12em; color: var(--acc, var(--lime));
    background: var(--acc-soft, rgba(182, 255, 60, 0.1)); border: 1px solid var(--acc-line, rgba(182, 255, 60, 0.3));
    box-shadow: 0 0 18px var(--acc-soft, rgba(182, 255, 60, 0.1));
}
.sec-bio  { --acc: var(--lime);   --acc-soft: rgba(182,255,60,.1);   --acc-line: rgba(182,255,60,.34);  --acc-glow: var(--glow-lime); }
.sec-food { --acc: var(--sun);    --acc-soft: rgba(255,212,38,.1);   --acc-line: rgba(255,212,38,.36);  --acc-glow: var(--glow-sun); }
.sec-doc  { --acc: var(--violet); --acc-soft: rgba(161,118,255,.12); --acc-line: rgba(161,118,255,.42); --acc-glow: var(--glow-violet); }

/* ============================================================
   HEADER + LOGO
   ============================================================ */
.cl-header {
    position: relative; overflow: hidden; display: flex; justify-content: space-between; align-items: center;
    gap: 24px; flex-wrap: wrap; padding: 28px 32px 58px; margin-bottom: 22px;
    background: linear-gradient(135deg, rgba(14, 30, 22, 0.82), rgba(6, 12, 10, 0.9));
    backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
    border: 1px solid var(--line); border-radius: 28px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55), 0 0 60px rgba(182, 255, 60, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    animation: cardIn 0.9s var(--ease-out) backwards;
}
.cl-header::before {
    content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px; z-index: 3;
    background: linear-gradient(90deg, transparent, var(--lime), var(--sun), var(--flare), transparent);
    background-size: 200% 100%; animation: sheen 6s linear infinite;
}
.cl-header::after {
    content: ""; position: absolute; left: 0; right: 0; bottom: 6px; height: 38px; pointer-events: none; z-index: 1; opacity: 0.9;
    background: url("__ECG__") left center / auto 38px repeat-x;
}
.cl-brand { position: relative; z-index: 2; display: flex; align-items: center; gap: 22px; }

.cl-logo {
    position: relative; width: 68px; height: 68px; flex-shrink: 0; display: grid; place-items: center; border-radius: 22px;
    background: radial-gradient(circle at 30% 25%, #10261b, #050c09);
    box-shadow: 0 10px 30px rgba(182, 255, 60, 0.22), inset 0 0 18px rgba(182, 255, 60, 0.1);
    transition: transform 0.6s var(--ease-spring), box-shadow 0.6s var(--ease-out);
}
.cl-logo::before {
    content: ""; position: absolute; inset: -2px; border-radius: 24px; padding: 2px; pointer-events: none;
    background: conic-gradient(from var(--ang), var(--lime), var(--sun), var(--flare), var(--violet), var(--mint), var(--lime));
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); -webkit-mask-composite: xor;
    mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); mask-composite: exclude;
    animation: spinAng 6s linear infinite;
}
.cl-logo:hover { transform: translateY(-4px) rotate(-5deg) scale(1.07); box-shadow: 0 16px 44px rgba(255, 212, 38, 0.32), inset 0 0 22px rgba(182, 255, 60, 0.2); }
.cl-logo img { width: 46px; height: 46px; }

.cl-chip {
    position: relative; z-index: 2; display: inline-flex; align-items: center; gap: 10px; padding: 9px 18px; border-radius: 999px;
    font-size: 0.8rem; font-weight: 700; letter-spacing: 0.04em; color: var(--lime);
    background: rgba(182, 255, 60, 0.08); border: 1px solid rgba(182, 255, 60, 0.38); box-shadow: 0 0 24px rgba(182, 255, 60, 0.14);
}
.cl-chip-dot { position: relative; width: 9px; height: 9px; border-radius: 50%; background: var(--lime); box-shadow: 0 0 10px var(--lime); }
.cl-chip-dot::after { content: ""; position: absolute; inset: -4px; border-radius: 50%; background: var(--lime); animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite; }

.cl-prefs { display: flex; flex-wrap: wrap; gap: 12px; margin: 0 0 30px; color: var(--muted); font-size: 1rem; animation: pageIn 1s var(--ease-out) 0.15s backwards; }
.cl-prefs span { display: inline-flex; align-items: center; gap: 10px; padding: 7px 7px 7px 16px; border-radius: 999px; background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); }
.cl-prefs strong { color: #06130b; font-weight: 700; padding: 5px 14px; border-radius: 999px; background: linear-gradient(120deg, var(--lime), var(--sun)); box-shadow: 0 0 18px rgba(182, 255, 60, 0.32); }

/* ============================================================
   GLASS CARDS  (state colours via --c1 / --c2 / --g / --spot)
   ============================================================ */
.metric-card, .food-card, .cl-summary, .ob-card {
    --c1: var(--mint); --c2: var(--lime); --g: var(--glow-mint); --spot: rgba(31, 242, 160, 0.16);
    position: relative; overflow: hidden; border-radius: 26px; border: 1px solid var(--line);
    background: linear-gradient(160deg, rgba(16, 32, 24, 0.8), rgba(6, 12, 10, 0.9));
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    box-shadow: 0 18px 44px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.07);
    animation: cardIn 0.85s var(--ease-out) backwards;
    transition: transform 0.5s var(--ease-out), box-shadow 0.5s var(--ease-out), border-color 0.5s;
}
.food-card { --c1: var(--sun); --c2: var(--lime); --g: var(--glow-sun); --spot: rgba(255, 212, 38, 0.15); }

.metric-card::before, .food-card::before, .cl-summary::before, .ob-card::before {
    content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1.5px; pointer-events: none; z-index: 5;
    background: conic-gradient(from var(--ang), transparent 0 55%, var(--c1) 75%, var(--c2) 88%, transparent 100%);
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); -webkit-mask-composite: xor;
    mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); mask-composite: exclude;
    opacity: 0; transition: opacity 0.5s; animation: spinAng 6s linear infinite; animation-play-state: paused;
}
.metric-card:hover::before, .food-card:hover::before, .metric-card.is-flagged::before, .metric-card.is-low::before,
.cl-summary::before, .ob-card::before { opacity: 1; animation-play-state: running; }

/* cursor spotlight (position set by the JS layer, falls back to a top glow) */
.metric-card::after, .food-card::after, .cl-summary::after, .ob-card::after {
    content: ""; position: absolute; inset: 0; border-radius: inherit; z-index: 1; pointer-events: none; opacity: 0; transition: opacity 0.5s;
    background: radial-gradient(380px circle at var(--mx, 50%) var(--my, 0%), var(--spot), transparent 62%);
}
.metric-card:hover::after, .food-card:hover::after, .cl-summary:hover::after, .ob-card:hover::after { opacity: 1; }

.metric-card, .food-card { transform-style: preserve-3d; }
.metric-card:hover, .food-card:hover {
    transform: perspective(1100px) rotateX(var(--rx, 0deg)) rotateY(var(--ry, 0deg)) translateY(-8px) scale(1.012);
    transition: transform 0.14s linear, box-shadow 0.5s var(--ease-out), border-color 0.5s;
    border-color: rgba(255, 255, 255, 0.24); z-index: 10;
    box-shadow: 0 32px 64px rgba(0, 0, 0, 0.62), 0 0 50px var(--g), inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

/* ============================================================
   BIOMARKER CARDS
   ============================================================ */
.metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 330px), 1fr)); gap: 26px; margin: 18px 0 40px; }
.metric-card { padding: 30px; display: flex; flex-direction: column; justify-content: space-between; }
.metric-card.is-flagged {
    --c1: var(--flare); --c2: var(--ember); --g: var(--glow-flare); --spot: rgba(255, 59, 114, 0.2); border-color: rgba(255, 59, 114, 0.42);
    background: linear-gradient(170deg, rgba(255, 59, 114, 0.12), rgba(8, 12, 10, 0.92) 55%);
}
.metric-card.is-low {
    --c1: var(--sun); --c2: var(--ember); --g: var(--glow-sun); --spot: rgba(255, 212, 38, 0.18); border-color: rgba(255, 212, 38, 0.42);
    background: linear-gradient(170deg, rgba(255, 212, 38, 0.11), rgba(8, 12, 10, 0.92) 55%);
}
.flag-bar {
    position: absolute; top: 0; left: 0; right: 0; height: 4px; z-index: 6;
    background: linear-gradient(90deg, var(--c1), var(--c2), var(--c1)); box-shadow: 0 0 22px var(--c1); animation: pulseBar 2.4s ease-in-out infinite;
}
.metric-head, .metric-value, .range, .metric-explain, .food-head, .food-body { position: relative; z-index: 3; }
.metric-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 22px; }
.metric-cat { margin: 0 0 8px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); }
.metric-name { margin: 0; padding: 0; font-size: 1.05rem; line-height: 1.4; font-weight: 600; color: var(--text); letter-spacing: -0.01em; }
.metric-value { display: flex; align-items: baseline; flex-wrap: wrap; gap: 10px; margin: 0 0 6px; }
.metric-number {
    font-size: clamp(2.2rem, 3.3vw, 3.1rem); font-weight: 700; line-height: 1; letter-spacing: -0.04em; color: var(--text);
    text-shadow: 0 0 14px var(--g), 0 0 42px var(--g); overflow-wrap: anywhere; font-variant-numeric: tabular-nums;
}
.metric-card.is-flagged .metric-number { color: var(--flare); }
.metric-card.is-low .metric-number { color: var(--sun); }
.metric-unit { font-size: 0.92rem; font-weight: 700; color: var(--muted); padding: 3px 11px; border-radius: 8px; background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.09); }
.metric-raw { font-size: 1.3rem; font-weight: 700; line-height: 1.5; color: var(--text); }

/* zoned range gauge */
.range { margin-top: 46px; padding: 0 10px; display: flex; flex-direction: column; gap: 14px; }
.range-track {
    position: relative; height: 10px; border-radius: 999px; overflow: visible;
    background: linear-gradient(90deg, rgba(255, 212, 38, 0.42) 0, rgba(255, 212, 38, 0.42) var(--lo, 0%), transparent var(--lo, 0%), transparent var(--hi, 100%), rgba(255, 59, 114, 0.42) var(--hi, 100%), rgba(255, 59, 114, 0.42) 100%), rgba(255, 255, 255, 0.06);
    box-shadow: inset 0 2px 5px rgba(0, 0, 0, 0.7);
}
.range-safe {
    position: absolute; top: 0; bottom: 0; border-radius: 999px; transform-origin: left center;
    background: linear-gradient(90deg, rgba(31, 242, 160, 0.55), rgba(182, 255, 60, 0.95), rgba(31, 242, 160, 0.55));
    box-shadow: 0 0 18px rgba(31, 242, 160, 0.5); animation: safeGrow 1.1s var(--ease-out) 0.3s backwards;
}
.range-marker {
    position: absolute; top: 50%; width: 18px; height: 18px; z-index: 4; border-radius: 50%; transform: translate(-50%, -50%); background: #fff;
    box-shadow: 0 0 0 4px var(--c1), 0 0 20px var(--c1), 0 0 42px var(--c1); animation: markerIn 1.4s var(--ease-spring) 0.35s backwards;
}
.range-tip {
    position: absolute; left: 50%; bottom: 26px; transform: translate(-50%, 0); padding: 4px 9px; border-radius: 8px; white-space: nowrap;
    font-size: 0.74rem; font-weight: 800; color: #06130b; background: var(--c1); box-shadow: 0 0 18px var(--c1);
    animation: tipBob 2.6s ease-in-out infinite;
}
.range-tip::after { content: ""; position: absolute; left: 50%; top: 100%; width: 8px; height: 8px; margin: -4px 0 0 -4px; background: var(--c1); transform: rotate(45deg); }
.range-labels { display: flex; justify-content: space-between; font-size: 0.74rem; font-weight: 700; color: var(--muted); }

.metric-explain { margin: 24px 0 0; padding-top: 22px; border-top: 1px dashed rgba(255, 255, 255, 0.18); font-size: 1.04rem; line-height: 1.7; color: rgba(242, 255, 245, 0.88); }
.metric-explain strong { display: block; margin-bottom: 8px; font-size: 0.86rem; font-weight: 700; letter-spacing: 0.03em; color: var(--c1); }

.pill {
    display: inline-flex; align-items: center; gap: 9px; padding: 7px 15px; border-radius: 999px; white-space: nowrap;
    font-size: 0.7rem; font-weight: 800; line-height: 1; letter-spacing: 0.14em; text-transform: uppercase;
    border: 1px solid transparent; box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.pill-dot { position: relative; width: 7px; height: 7px; border-radius: 50%; background: currentColor; box-shadow: 0 0 10px currentColor; }
.pill-dot::after { content: ""; position: absolute; inset: -2px; border-radius: 50%; background: currentColor; opacity: 0; animation: pingSoft 2.2s infinite; }
.pill-normal { background: rgba(31, 242, 160, 0.13); color: var(--mint); border-color: rgba(31, 242, 160, 0.45); box-shadow: 0 0 22px rgba(31, 242, 160, 0.22); }
.pill-high   { background: rgba(255, 59, 114, 0.13); color: var(--flare); border-color: rgba(255, 59, 114, 0.5); box-shadow: 0 0 22px rgba(255, 59, 114, 0.28); }
.pill-low    { background: rgba(255, 212, 38, 0.13); color: var(--sun); border-color: rgba(255, 212, 38, 0.5); box-shadow: 0 0 22px rgba(255, 212, 38, 0.25); }

/* ============================================================
   SUMMARY PANEL
   ============================================================ */
.cl-summary {
    --c1: var(--lime); --c2: var(--sun); --g: var(--glow-lime); --spot: rgba(182, 255, 60, 0.11);
    padding: 40px; display: grid; gap: 30px; margin: 14px 0 38px; border-radius: 30px; border-color: rgba(182, 255, 60, 0.28);
    background:
        radial-gradient(60% 90% at 100% 0%, rgba(182, 255, 60, 0.15), transparent 60%),
        radial-gradient(50% 80% at 0% 100%, rgba(255, 212, 38, 0.09), transparent 60%),
        linear-gradient(160deg, rgba(14, 28, 21, 0.86), rgba(5, 10, 8, 0.93));
    box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6), inset 0 0 60px rgba(182, 255, 60, 0.05);
}
.cl-summary > * { position: relative; z-index: 2; }
.cl-sum-main { display: flex; align-items: center; justify-content: space-between; gap: 40px; flex-wrap: wrap; }
.cl-sum-copy { flex: 1 1 320px; min-width: 0; }
.cl-summary-text { margin: 0; max-width: 68ch; font-size: 1.2rem; line-height: 1.8; font-weight: 400; color: var(--text); }

.cl-ring {
    position: relative; width: 170px; aspect-ratio: 1; flex-shrink: 0; margin: 12px; border-radius: 50%;
    display: grid; place-content: center; justify-items: center; gap: 2px; text-align: center;
    background: conic-gradient(var(--mint) 0, var(--lime) calc(var(--pct) * 0.5%), var(--sun) calc(var(--pct) * 1%), rgba(255, 255, 255, 0.07) calc(var(--pct) * 1%) 100%);
    box-shadow: 0 0 40px rgba(182, 255, 60, 0.28), 0 0 90px rgba(31, 242, 160, 0.12);
    animation: ringFill 1.8s var(--ease-out) 0.3s backwards;
}
.cl-ring::before { content: ""; position: absolute; inset: 14px; border-radius: 50%; background: radial-gradient(circle at 50% 35%, #0c1f15, #050d09); box-shadow: inset 0 0 28px rgba(0, 0, 0, 0.85); }
.cl-ring::after {
    content: ""; position: absolute; inset: -12px; border-radius: 50%; opacity: 0.65; pointer-events: none;
    background: repeating-conic-gradient(from 0deg, rgba(182, 255, 60, 0.7) 0 0.9deg, transparent 0.9deg 7.5deg);
    -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 7px), #000 calc(100% - 6px));
    mask: radial-gradient(farthest-side, transparent calc(100% - 7px), #000 calc(100% - 6px));
    animation: spinSlow 50s linear infinite;
}
.cl-ring > * { position: relative; z-index: 2; }
.cl-ring-val { font-size: 1.9rem; font-weight: 700; line-height: 1; color: var(--lime); text-shadow: 0 0 22px var(--glow-lime); }
.cl-ring-val::after { content: counter(n) "%"; }
.cl-ring-label { max-width: 96px; font-size: 0.72rem; font-weight: 500; line-height: 1.25; color: var(--muted); }

.cl-count { counter-reset: n var(--n); animation: countUp 1.6s var(--ease-out) 0.4s backwards; }
.cl-count::after { content: counter(n); }
.cl-ring-val.cl-count::after { content: counter(n) "%"; }

.cl-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 18px; }
.cl-stat {
    --s: var(--lime); --sg: var(--glow-lime);
    position: relative; overflow: hidden; display: flex; flex-direction: column; gap: 10px; padding: 22px 24px 22px 28px; border-radius: 20px;
    background: rgba(0, 0, 0, 0.35); border: 1px solid rgba(255, 255, 255, 0.08);
    transition: transform 0.45s var(--ease-spring), border-color 0.3s, box-shadow 0.4s;
}
.cl-stat::before { content: ""; position: absolute; left: 0; top: 18%; bottom: 18%; width: 3px; border-radius: 0 3px 3px 0; background: var(--s); box-shadow: 0 0 14px var(--s); }
.cl-stat::after { content: ""; position: absolute; inset: 0; pointer-events: none; background: radial-gradient(240px circle at var(--mx, 50%) var(--my, 0%), var(--sg), transparent 70%); opacity: 0; transition: opacity 0.4s; }
.cl-stat:hover::after { opacity: 0.55; }
.cl-stat-total { --s: var(--sun); --sg: var(--glow-sun); }
.cl-stat-normal { --s: var(--mint); --sg: var(--glow-mint); }
.cl-stat-flagged { --s: var(--flare); --sg: var(--glow-flare); }
.cl-stat:hover { transform: translateY(-5px); border-color: var(--s); box-shadow: 0 14px 32px rgba(0, 0, 0, 0.5), 0 0 30px var(--sg); }
.cl-stat-label { position: relative; z-index: 1; font-size: 0.9rem; font-weight: 500; letter-spacing: 0.02em; color: var(--muted); }
.cl-stat-value { position: relative; z-index: 1; font-size: 2.6rem; font-weight: 700; line-height: 1; color: var(--s); text-shadow: 0 0 12px var(--sg), 0 0 34px var(--sg); }

/* per-category segmented health strip */
.cl-systems { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; }
.cl-sys { position: relative; overflow: hidden; padding: 16px 18px; border-radius: 16px; background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255, 255, 255, 0.07); transition: border-color 0.3s, transform 0.4s var(--ease-spring); }
.cl-sys:hover { transform: translateY(-3px); border-color: var(--line-hi); }
.cl-sys-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; margin-bottom: 12px; }
.cl-sys-name { font-size: 0.95rem; font-weight: 600; color: var(--text); overflow-wrap: anywhere; }
.cl-sys-n { font-size: 0.78rem; font-weight: 700; color: var(--muted); flex-shrink: 0; }
.cl-seg-row { display: flex; gap: 5px; height: 10px; }
.cl-seg { flex: 1; border-radius: 4px; transform-origin: bottom; animation: segIn 0.7s var(--ease-spring) backwards; }
.cl-seg-normal { background: var(--mint); box-shadow: 0 0 10px var(--glow-mint); }
.cl-seg-low { background: var(--sun); box-shadow: 0 0 10px var(--glow-sun); }
.cl-seg-high { background: var(--flare); box-shadow: 0 0 10px var(--glow-flare); }

.cl-flag-list { display: flex; flex-wrap: wrap; gap: 10px; }
.cl-flag-tag {
    padding: 7px 14px; border-radius: 999px; font-size: 0.9rem; font-weight: 500; color: #ffe3bd; background: rgba(255, 138, 36, 0.1);
    border: 1px solid rgba(255, 138, 36, 0.42); box-shadow: 0 0 18px rgba(255, 138, 36, 0.14); transition: transform 0.35s var(--ease-spring), box-shadow 0.35s;
}
.cl-flag-tag:hover { transform: translateY(-3px) scale(1.04); box-shadow: 0 0 26px rgba(255, 138, 36, 0.38); }

/* ============================================================
   FOOD CARDS
   ============================================================ */
.food-card { padding: 32px; display: flex; flex-direction: column; gap: 18px; }
.food-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding-bottom: 18px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
.food-title { margin: 0; padding: 0; font-size: 1.05rem; font-weight: 600; line-height: 1.4; color: var(--text); }
.food-body { margin: 0; font-size: 1.08rem; line-height: 1.85; color: rgba(242, 255, 245, 0.92); white-space: pre-line; }

/* ============================================================
   DOCTOR QUESTION ACCORDIONS
   ============================================================ */
.dq-list { display: flex; flex-direction: column; gap: 16px; margin-top: 22px; }
details.dq {
    position: relative; border-radius: 22px; overflow: hidden; border: 1px solid rgba(255, 255, 255, 0.09);
    background: rgba(10, 18, 14, 0.72); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
    animation: cardIn 0.7s var(--ease-out) backwards; transition: border-color 0.4s, box-shadow 0.5s, background 0.5s;
}
details.dq:hover { border-color: rgba(255, 255, 255, 0.2); }
details.dq[open] { border-color: var(--acc-line, rgba(161, 118, 255, 0.42)); background: rgba(12, 22, 17, 0.88); box-shadow: 0 18px 44px rgba(0, 0, 0, 0.5), 0 0 40px var(--acc-soft, rgba(161, 118, 255, 0.12)); }
details.dq::details-content { block-size: 0; overflow: hidden; transition: block-size 0.55s var(--ease-out), content-visibility 0.55s allow-discrete; }
details.dq[open]::details-content { block-size: auto; }
details.dq summary { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 22px 26px; cursor: pointer; list-style: none; user-select: none; transition: background 0.3s; }
details.dq summary:hover { background: rgba(255, 255, 255, 0.04); }
details.dq summary::-webkit-details-marker { display: none; }
details.dq summary:focus-visible { outline: 2px solid var(--acc, var(--violet)); outline-offset: -4px; }
.dq-left { display: flex; align-items: center; gap: 20px; min-width: 0; }
.dq-count {
    flex-shrink: 0; width: 44px; height: 44px; display: grid; place-items: center; border-radius: 13px; font-size: 1rem; font-weight: 800; color: var(--acc, var(--violet));
    background: var(--acc-soft, rgba(161, 118, 255, 0.12)); border: 1px solid var(--acc-line, rgba(161, 118, 255, 0.42)); box-shadow: 0 0 20px var(--acc-soft, rgba(161, 118, 255, 0.12));
}
.dq-name { font-size: 1.02rem; font-weight: 600; color: var(--text); overflow-wrap: anywhere; }
.dq-right { display: flex; align-items: center; gap: 18px; }
.dq-chev { display: block; width: 11px; height: 11px; margin: -5px 6px 0 0; border-right: 3px solid currentColor; border-bottom: 3px solid currentColor; color: var(--muted); transform: rotate(45deg); transition: transform 0.6s var(--ease-spring), color 0.3s; }
details.dq[open] .dq-chev { transform: translateY(5px) rotate(225deg); color: var(--acc, var(--violet)); filter: drop-shadow(0 0 8px var(--acc, var(--violet))); }
.pill-arrow { width: 0; height: 0; border-left: 4.5px solid transparent; border-right: 4.5px solid transparent; }
.pill-arrow.up { border-bottom: 7px solid currentColor; }
.pill-arrow.down { border-top: 7px solid currentColor; }
.dq-body { padding: 0 26px 26px; }
details.dq[open] .dq-body { animation: dqIn 0.55s var(--ease-out) backwards; }
.dq-body ol { list-style: none; counter-reset: q; margin: 0; padding: 22px 0 0; display: flex; flex-direction: column; gap: 14px; border-top: 1px dashed rgba(255, 255, 255, 0.15); }
.dq-body li {
    counter-increment: q; display: flex; gap: 20px; padding: 20px 24px; border-radius: 16px; font-size: 1.05rem; line-height: 1.7; color: rgba(242, 255, 245, 0.94);
    background: rgba(0, 0, 0, 0.42); border: 1px solid rgba(255, 255, 255, 0.07);
    transition: transform 0.4s var(--ease-out), background 0.4s, border-color 0.4s, box-shadow 0.4s;
}
details.dq[open] .dq-body li { animation: liIn 0.6s var(--ease-out) backwards; }
details.dq[open] .dq-body li:nth-child(1) { animation-delay: 0.10s; }
details.dq[open] .dq-body li:nth-child(2) { animation-delay: 0.18s; }
details.dq[open] .dq-body li:nth-child(3) { animation-delay: 0.26s; }
details.dq[open] .dq-body li:nth-child(4) { animation-delay: 0.34s; }
details.dq[open] .dq-body li:nth-child(5) { animation-delay: 0.42s; }
.dq-body li:hover { transform: translateX(8px); background: var(--acc-soft, rgba(161, 118, 255, 0.1)); border-color: var(--acc-line, rgba(161, 118, 255, 0.42)); box-shadow: 0 10px 24px rgba(0, 0, 0, 0.4); }
.dq-body li::before {
    content: counter(q, decimal-leading-zero); flex-shrink: 0; height: fit-content; padding: 3px 10px; border-radius: 8px; font-size: 0.9rem; font-weight: 800; line-height: 1.6;
    color: var(--acc, var(--violet)); background: var(--acc-soft, rgba(161, 118, 255, 0.12)); border: 1px solid var(--acc-line, rgba(161, 118, 255, 0.42));
}

/* ============================================================
   TABS  (new React-Aria DOM and the older BaseWeb DOM)
   ============================================================ */
[data-testid="stTabs"] [role="tablist"], .stTabs [data-baseweb="tab-list"] {
    display: inline-flex; gap: 8px; padding: 8px; margin-bottom: 34px; border-radius: 22px; position: relative; max-width: 100%;
    background: rgba(8, 16, 12, 0.74); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    border: 1px solid var(--line); box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.07);
}
[data-testid="stTabs"] [role="tab"], .stTabs [data-baseweb="tab"] {
    position: relative; height: auto; padding: 13px 26px; border-radius: 15px; border: none; background: transparent; cursor: pointer; color: var(--muted);
    transition: color 0.3s, background 0.4s, box-shadow 0.4s, transform 0.4s var(--ease-spring);
}
[data-testid="stTabs"] [role="tab"] p, .stTabs [data-baseweb="tab"] p { margin: 0; font-size: 1.02rem; font-weight: 600; color: inherit !important; }
[data-testid="stTabs"] [role="tab"]:hover, .stTabs [data-baseweb="tab"]:hover { color: var(--text); background: rgba(255, 255, 255, 0.05); transform: translateY(-2px); }
[data-testid="stTabs"] [role="tab"][aria-selected="true"], .stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #fff; background: linear-gradient(135deg, rgba(182, 255, 60, 0.2), rgba(182, 255, 60, 0.04));
    box-shadow: 0 0 28px rgba(182, 255, 60, 0.22), inset 0 0 0 1px rgba(182, 255, 60, 0.5);
}
[data-testid="stTabs"] [role="tab"]:nth-child(2)[aria-selected="true"], .stTabs [data-baseweb="tab"]:nth-of-type(2)[aria-selected="true"] {
    background: linear-gradient(135deg, rgba(255, 212, 38, 0.2), rgba(255, 212, 38, 0.04)); box-shadow: 0 0 28px rgba(255, 212, 38, 0.22), inset 0 0 0 1px rgba(255, 212, 38, 0.5);
}
[data-testid="stTabs"] [role="tab"]:nth-child(3)[aria-selected="true"], .stTabs [data-baseweb="tab"]:nth-of-type(3)[aria-selected="true"] {
    background: linear-gradient(135deg, rgba(161, 118, 255, 0.22), rgba(161, 118, 255, 0.04)); box-shadow: 0 0 28px rgba(161, 118, 255, 0.24), inset 0 0 0 1px rgba(161, 118, 255, 0.55);
}
.react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"] {
    height: 3px !important; border-radius: 3px; background: linear-gradient(90deg, var(--lime), var(--sun), var(--flare)) !important; box-shadow: 0 0 14px var(--lime);
}
.stTabs [data-baseweb="tab-border"] { display: none; }
[data-testid="stTabs"] [role="tabpanel"], .stTabs [data-baseweb="tab-panel"] { padding-top: 0; animation: panelIn 0.65s var(--ease-out) backwards; }

/* ============================================================
   BUTTONS
   ============================================================ */
.stButton button, .stDownloadButton button, [data-testid="stDownloadButton"] button {
    position: relative; overflow: hidden; padding: 0.85rem 1.7rem !important; border: 0 !important; border-radius: 16px !important;
    color: #06130b !important; font-size: 1.05rem !important; font-weight: 700 !important; letter-spacing: 0.02em;
    background: linear-gradient(120deg, var(--lime) 0%, var(--sun) 55%, var(--ember) 100%) !important; background-size: 200% 100% !important;
    box-shadow: 0 10px 28px rgba(182, 255, 60, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.55) !important;
    transition: transform 0.45s var(--ease-spring), box-shadow 0.45s var(--ease-out), background-position 0.6s var(--ease-out) !important;
}
.stButton button p, .stDownloadButton button p, .stButton button span, .stDownloadButton button span, [data-testid="stDownloadButton"] button p { color: #06130b !important; font-weight: 700 !important; }
.stButton button:hover, .stDownloadButton button:hover, [data-testid="stDownloadButton"] button:hover {
    transform: translateY(-4px) scale(1.02) !important; background-position: 100% 0 !important;
    box-shadow: 0 18px 40px rgba(255, 212, 38, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.6) !important;
}
.stButton button:active, .stDownloadButton button:active { transform: translateY(1px) scale(0.98) !important; }
.stButton button:focus-visible, .stDownloadButton button:focus-visible { outline: 2px solid var(--lime) !important; outline-offset: 3px !important; }

.st-key-change_prefs button { background: rgba(255, 255, 255, 0.04) !important; border: 1px solid var(--line) !important; box-shadow: none !important; backdrop-filter: blur(10px); }
.st-key-change_prefs button p, .st-key-change_prefs button span { color: var(--text) !important; }
.st-key-change_prefs button:hover { background: rgba(182, 255, 60, 0.1) !important; border-color: var(--line-hi) !important; box-shadow: 0 10px 30px rgba(182, 255, 60, 0.22) !important; }

/* ============================================================
   UPLOADER (HUD brackets + laser scan)
   ============================================================ */
[data-testid="stFileUploader"] { position: relative; padding: 6px; }
[data-testid="stFileUploader"]::before {
    content: ""; position: absolute; inset: -4px; z-index: 3; pointer-events: none;
    background:
        linear-gradient(var(--lime), var(--lime)) top left / 30px 2px no-repeat,    linear-gradient(var(--lime), var(--lime)) top left / 2px 30px no-repeat,
        linear-gradient(var(--sun), var(--sun)) top right / 30px 2px no-repeat,     linear-gradient(var(--sun), var(--sun)) top right / 2px 30px no-repeat,
        linear-gradient(var(--mint), var(--mint)) bottom left / 30px 2px no-repeat, linear-gradient(var(--mint), var(--mint)) bottom left / 2px 30px no-repeat,
        linear-gradient(var(--ember), var(--ember)) bottom right / 30px 2px no-repeat, linear-gradient(var(--ember), var(--ember)) bottom right / 2px 30px no-repeat;
    filter: drop-shadow(0 0 5px rgba(182, 255, 60, 0.7)); animation: bracket 3s ease-in-out infinite;
}
.stApp [data-testid="stFileUploaderDropzone"] {
    position: relative; overflow: hidden; min-height: 210px; display: flex !important; flex-direction: column; align-items: center; justify-content: center !important; gap: 14px;
    border-radius: 22px !important; border: 1.5px dashed rgba(182, 255, 60, 0.42) !important;
    background:
        repeating-radial-gradient(circle at 50% 50%, rgba(182, 255, 60, 0.09) 0 1px, transparent 1px 44px),
        radial-gradient(70% 90% at 50% 0%, rgba(182, 255, 60, 0.09), transparent 70%), rgba(5, 12, 9, 0.74) !important;
    backdrop-filter: blur(16px); transition: border-color 0.4s, box-shadow 0.5s, transform 0.5s var(--ease-spring) !important;
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--lime) !important; transform: scale(1.01); box-shadow: 0 0 44px rgba(182, 255, 60, 0.22), inset 0 0 36px rgba(182, 255, 60, 0.08) !important; }
[data-testid="stFileUploaderDropzone"] > * { position: relative; z-index: 2; }
.stApp [data-testid="stFileUploaderDropzoneInstructions"], .stApp [data-testid="stFileUploaderDropzoneInstructions"] > div { flex: 0 1 auto !important; text-align: center; margin: 0 !important; }
/* radar sweep */
[data-testid="stFileUploaderDropzone"]::before {
    content: ""; position: absolute; left: 50%; top: 50%; width: 1100px; height: 1100px; margin: -550px 0 0 -550px; border-radius: 50%; pointer-events: none;
    background: conic-gradient(from var(--ang), transparent 0 80%, rgba(182, 255, 60, 0.16) 94%, rgba(255, 212, 38, 0.34) 100%);
    -webkit-mask: radial-gradient(circle, #000 0 40%, transparent 62%); mask: radial-gradient(circle, #000 0 40%, transparent 62%);
    animation: spinAng 5s linear infinite;
}
[data-testid="stFileUploaderDropzone"]::after {
    content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px; pointer-events: none; z-index: 1; opacity: 0.7;
    background: linear-gradient(90deg, transparent, var(--lime), var(--sun), transparent); box-shadow: 0 0 18px var(--lime), 0 0 36px rgba(255, 212, 38, 0.6);
    animation: laser 4s var(--ease-smooth) infinite;
}
[data-testid="stFileUploaderDropzone"] span, [data-testid="stFileUploaderDropzone"] small, [data-testid="stFileUploaderDropzoneInstructions"] * { color: var(--muted) !important; }
[data-testid="stFileUploaderDropzone"] svg { color: var(--lime) !important; fill: var(--lime) !important; filter: drop-shadow(0 0 8px var(--glow-lime)); }
[data-testid="stFileUploaderDropzone"] button {
    color: var(--lime) !important; font-weight: 700 !important; border-radius: 12px !important; background: rgba(182, 255, 60, 0.1) !important; border: 1px solid rgba(182, 255, 60, 0.5) !important;
    box-shadow: none !important; transition: background 0.3s, color 0.3s, transform 0.4s var(--ease-spring), box-shadow 0.3s !important;
}
[data-testid="stFileUploaderDropzone"] button p, [data-testid="stFileUploaderDropzone"] button span { color: inherit !important; }
[data-testid="stFileUploaderDropzone"] button:hover { background: var(--lime) !important; color: #06130b !important; transform: translateY(-2px) !important; box-shadow: 0 8px 24px rgba(182, 255, 60, 0.4) !important; }
[data-testid="stFileUploaderFile"] { border-radius: 14px; background: rgba(182, 255, 60, 0.06); border: 1px solid var(--line); animation: panelIn 0.5s var(--ease-out) backwards; }
[data-testid="stFileUploaderFile"] * { color: var(--text) !important; }

/* ============================================================
   RADIO OPTIONS (onboarding), ALERTS, SPINNER, FOOTER
   ============================================================ */
[data-testid="stRadioGroup"], div[role="radiogroup"] { gap: 10px; margin-top: 18px; display: flex; flex-direction: column; }
.stApp .stElementContainer:has([data-testid="stRadio"]), .stApp [data-testid="stRadio"], .stApp [data-testid="stRadioGroup"] { width: 100% !important; }
.stApp [data-testid="stRadioGroup"] { align-items: stretch !important; }
.stApp [data-testid="stRadioGroup"] > div { width: 100% !important; }
.stApp [data-testid="stRadioOption"], div[role="radiogroup"] > label {
    position: relative; display: flex; width: 100% !important; box-sizing: border-box; margin: 0; padding: 16px 52px 16px 20px !important; border-radius: 16px; cursor: pointer;
    background: rgba(10, 20, 15, 0.72); border: 1px solid var(--line);
    transition: transform 0.4s var(--ease-spring), border-color 0.3s, box-shadow 0.4s, background 0.4s;
}
.stApp [data-testid="stRadioOption"] > div > div:first-child, div[role="radiogroup"] > label > div:first-child { display: none !important; }
[data-testid="stRadioOption"] p, div[role="radiogroup"] > label p { margin: 0; font-size: 1.1rem; font-weight: 500; color: var(--text) !important; }
[data-testid="stRadioOption"]::after, div[role="radiogroup"] > label::after {
    content: ""; position: absolute; right: 20px; top: 50%; width: 16px; height: 16px; margin-top: -8px; border-radius: 50%;
    border: 2px solid rgba(255, 255, 255, 0.28); transition: all 0.4s var(--ease-spring);
}
[data-testid="stRadioOption"]:hover, div[role="radiogroup"] > label:hover { transform: translateX(6px); border-color: var(--line-hi); box-shadow: 0 0 24px rgba(182, 255, 60, 0.16); }
[data-testid="stRadioOption"][data-selected="true"], div[role="radiogroup"] > label:has(input:checked) {
    border-color: var(--lime); background: linear-gradient(90deg, rgba(182, 255, 60, 0.16), rgba(255, 212, 38, 0.05));
    box-shadow: 0 0 0 1px rgba(182, 255, 60, 0.35), 0 0 34px rgba(182, 255, 60, 0.22);
}
[data-testid="stRadioOption"][data-selected="true"]::after, div[role="radiogroup"] > label:has(input:checked)::after {
    border-color: var(--lime); background: var(--lime); box-shadow: 0 0 14px var(--lime), inset 0 0 0 3px #06130b;
}

[data-testid="stAlert"] { border-radius: 18px; background: rgba(10, 20, 16, 0.74) !important; border: 1px solid var(--line); backdrop-filter: blur(14px); animation: panelIn 0.6s var(--ease-out) backwards; }
[data-testid="stAlert"] p, [data-testid="stAlert"] span { color: var(--text) !important; }
.stSpinner, [data-testid="stSpinner"] {
    display: flex; align-items: center; gap: 14px; margin: 18px 0; padding: 16px 22px; border-radius: 16px;
    background: rgba(182, 255, 60, 0.06); border: 1px solid rgba(182, 255, 60, 0.3); box-shadow: 0 0 30px rgba(182, 255, 60, 0.12); animation: panelIn 0.5s var(--ease-out) backwards;
}
.stSpinner p, [data-testid="stSpinner"] p, .stSpinner span, [data-testid="stSpinner"] span { color: var(--lime) !important; font-weight: 500; }
.stSpinner, [data-testid="stSpinner"] { position: relative; overflow: hidden; }
.stSpinner::after, [data-testid="stSpinner"]::after {
    content: ""; position: absolute; bottom: 0; left: -40%; width: 40%; height: 3px; border-radius: 3px; pointer-events: none;
    background: linear-gradient(90deg, transparent, var(--lime), var(--sun), transparent); box-shadow: 0 0 16px var(--lime); animation: scanBar 1.6s var(--ease-smooth) infinite;
}

.cl-empty {
    margin-top: 22px; padding: 22px; text-align: center; font-size: 1.1rem; border-radius: 18px; color: var(--sun);
    background: rgba(255, 212, 38, 0.08); border: 1px solid rgba(255, 212, 38, 0.4); box-shadow: 0 0 30px rgba(255, 212, 38, 0.15); animation: panelIn 0.6s var(--ease-out) backwards;
}
.cl-footer { margin-top: 90px; padding: 36px 0 48px; text-align: center; font-size: 0.92rem; line-height: 1.7; color: #647d70; border-top: 1px dashed rgba(255, 255, 255, 0.14); animation: pageIn 1s var(--ease-out) 0.3s backwards; }

/* ============================================================
   ONBOARDING CARD
   ============================================================ */
.ob-card {
    --c1: var(--lime); --c2: var(--sun); --g: var(--glow-lime); --spot: rgba(182, 255, 60, 0.12);
    max-width: 640px; margin: 28px auto 0; padding: 56px 44px; text-align: center; border-radius: 32px; border-color: rgba(182, 255, 60, 0.3);
    background: radial-gradient(70% 60% at 50% 0%, rgba(182, 255, 60, 0.13), transparent 65%), linear-gradient(180deg, rgba(15, 28, 21, 0.86), rgba(5, 10, 8, 0.95));
    box-shadow: 0 30px 80px rgba(0, 0, 0, 0.65), 0 0 80px rgba(182, 255, 60, 0.07), inset 0 0 60px rgba(182, 255, 60, 0.06);
    animation: floatY 9s ease-in-out infinite, cardIn 0.9s var(--ease-out) backwards;
}
.ob-card > * { position: relative; z-index: 2; }
.ob-card .cl-logo { margin: 0 auto 32px; transform: scale(1.25); }
.ob-card:hover .cl-logo { transform: scale(1.35) rotate(-6deg); }
.ob-step { display: inline-block; margin-bottom: 22px; padding: 8px 20px; border-radius: 999px; font-size: 0.78rem; font-weight: 800; letter-spacing: 0.22em; color: var(--lime); background: rgba(182, 255, 60, 0.1); border: 1px solid rgba(182, 255, 60, 0.38); box-shadow: 0 0 22px rgba(182, 255, 60, 0.16); }
.ob-title { margin: 0 0 20px; padding: 0; font-size: 2rem; line-height: 1.25; font-weight: 700; letter-spacing: -0.03em; color: var(--text); }
.ob-desc { margin: 0 auto; max-width: 480px; font-size: 1.12rem; line-height: 1.75; color: var(--muted); }

/* ============================================================
   RESPONSIVE + REDUCED MOTION
   ============================================================ */
@media (max-width: 900px) {
    [data-testid="stMainBlockContainer"], .block-container { padding-left: 1rem !important; padding-right: 1rem !important; padding-top: 3.2rem !important; }
    .cl-header { padding: 22px 20px 38px; }
    .cl-title { font-size: 1.6rem; }
    .cl-h2 { font-size: 1.45rem; }
    .cl-summary { padding: 26px; }
    .cl-ring { width: 140px; }
    .ob-card { padding: 40px 24px; }
    .ob-title { font-size: 1.5rem; }
    [data-testid="stTabs"] [role="tablist"], .stTabs [data-baseweb="tab-list"] { display: flex; overflow-x: auto; }
    [data-testid="stTabs"] [role="tab"], .stTabs [data-baseweb="tab"] { padding: 11px 16px; white-space: nowrap; }
}
@media (max-width: 560px) {
    .metric-card, .food-card { padding: 24px; }
    .dq-body li { padding: 16px 18px; font-size: 1rem; gap: 14px; }
    .dq-name { font-size: 0.98rem; }
    .cl-stat-value { font-size: 2.1rem; }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: 0.001ms !important; animation-iteration-count: 1 !important; transition-duration: 0.001ms !important; scroll-behavior: auto !important; }
}
</style>
""".replace("__ECG__", ECG_URI)
render_html(THEME_CSS)

# ---------------------------------------------------------
# JS effects layer: particle network, cursor spotlight, 3D tilt, number count-up.
# Pure enhancement - the page looks complete without it.
# (No less-than signs anywhere in this block: Streamlit's sanitiser rejects them.)
# ---------------------------------------------------------
FX_JS = r"""(function (win, doc) {
  if (win.__clFx) { return; }
  win.__clFx = true;
  var reduce = win.matchMedia && win.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- particle network background ---------- */
  function particles() {
    var host = doc.querySelector('.stApp') || doc.body;
    if (doc.getElementById('cl-particles')) { return; }
    var cv = doc.createElement('canvas');
    cv.id = 'cl-particles';
    cv.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:0;pointer-events:none;opacity:0.85';
    host.insertBefore(cv, host.firstChild);
    var ctx = cv.getContext('2d');
    var dpr = Math.min(win.devicePixelRatio || 1, 2);
    var W = 0, H = 0, pts = [], mouse = { x: -9999, y: -9999 };
    var COLORS = ['182,255,60', '255,212,38', '31,242,160', '255,59,114', '161,118,255'];
    function size() {
      W = win.innerWidth; H = win.innerHeight;
      cv.width = W * dpr; cv.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var n = Math.max(26, Math.min(74, Math.floor((W * H) / 24000)));
      pts = [];
      while (n--) {
        pts.push({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4,
                   r: Math.random() * 1.7 + 0.7, c: COLORS[Math.floor(Math.random() * COLORS.length)] });
      }
    }
    function draw() {
      ctx.clearRect(0, 0, W, H);
      var i, j, p, q, dx, dy, d, a, n = pts.length;
      for (i = 0; n > i; i++) {
        p = pts[i];
        dx = mouse.x - p.x; dy = mouse.y - p.y; d = Math.sqrt(dx * dx + dy * dy);
        if (d > 1 && 190 > d) { p.vx += (dx / d) * 0.006; p.vy += (dy / d) * 0.006; }
        p.vx *= 0.995; p.vy *= 0.995;
        p.x += p.vx; p.y += p.vy;
        if (p.x > W + 20) { p.x = -20; } else if (-20 > p.x) { p.x = W + 20; }
        if (p.y > H + 20) { p.y = -20; } else if (-20 > p.y) { p.y = H + 20; }
      }
      for (i = 0; n > i; i++) {
        p = pts[i];
        for (j = i + 1; n > j; j++) {
          q = pts[j]; dx = p.x - q.x; dy = p.y - q.y; d = Math.sqrt(dx * dx + dy * dy);
          if (140 > d) {
            a = (1 - d / 140) * 0.2;
            ctx.strokeStyle = 'rgba(' + p.c + ',' + a.toFixed(3) + ')';
            ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); ctx.stroke();
          }
        }
        dx = p.x - mouse.x; dy = p.y - mouse.y; d = Math.sqrt(dx * dx + dy * dy);
        if (180 > d) {
          a = (1 - d / 180) * 0.45;
          ctx.strokeStyle = 'rgba(182,255,60,' + a.toFixed(3) + ')';
          ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
        }
      }
      for (i = 0; n > i; i++) {
        p = pts[i];
        ctx.shadowColor = 'rgba(' + p.c + ',0.9)'; ctx.shadowBlur = 10;
        ctx.fillStyle = 'rgba(' + p.c + ',0.8)';
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.2832); ctx.fill();
      }
      ctx.shadowBlur = 0;
    }
    function loop() {
      if (!doc.hidden) { draw(); }
      win.requestAnimationFrame(loop);
    }
    size();
    win.addEventListener('resize', size);
    doc.addEventListener('mousemove', function (e) { mouse.x = e.clientX; mouse.y = e.clientY; }, { passive: true });
    doc.addEventListener('mouseleave', function () { mouse.x = -9999; mouse.y = -9999; });
    if (reduce) { draw(); } else { loop(); }
  }

  /* ---------- cursor spotlight + 3D tilt ---------- */
  var SPOT = '.metric-card,.food-card,.cl-summary,.cl-stat,.ob-card';
  doc.addEventListener('mousemove', function (e) {
    var t = e.target;
    var el = t && t.closest ? t.closest(SPOT) : null;
    if (!el) { return; }
    var r = el.getBoundingClientRect();
    var x = e.clientX - r.left, y = e.clientY - r.top;
    el.style.setProperty('--mx', x + 'px');
    el.style.setProperty('--my', y + 'px');
    if (!reduce && (el.classList.contains('metric-card') || el.classList.contains('food-card'))) {
      el.style.setProperty('--ry', ((x / r.width - 0.5) * 10).toFixed(2) + 'deg');
      el.style.setProperty('--rx', ((0.5 - y / r.height) * 10).toFixed(2) + 'deg');
    }
  }, { passive: true });
  doc.addEventListener('mouseout', function (e) {
    var t = e.target;
    var el = t && t.closest ? t.closest('.metric-card,.food-card') : null;
    if (el && !el.contains(e.relatedTarget)) { el.style.setProperty('--rx', '0deg'); el.style.setProperty('--ry', '0deg'); }
  }, true);

  /* ---------- count-up for big biomarker numbers ---------- */
  function countUp(el) {
    if (el.getAttribute('data-cu')) { return; }
    el.setAttribute('data-cu', '1');
    var txt = el.textContent.trim();
    var v = parseFloat(txt);
    if (isNaN(v) || reduce) { return; }
    var dec = (txt.split('.')[1] || '').replace(/[^0-9]/g, '').length;
    var t0 = null, dur = 1200;
    function step(t) {
      if (t0 === null) { t0 = t; }
      var p = Math.min(1, (t - t0) / dur);
      var e = 1 - Math.pow(1 - p, 4);
      if (1 > p) { el.textContent = (v * e).toFixed(dec); win.requestAnimationFrame(step); } else { el.textContent = txt; }
    }
    el.textContent = (0).toFixed(dec);
    win.requestAnimationFrame(step);
  }
  var io = win.IntersectionObserver ? new win.IntersectionObserver(function (entries) {
    entries.forEach(function (en) { if (en.isIntersecting) { countUp(en.target); io.unobserve(en.target); } });
  }, { threshold: 0.4 }) : null;
  function scan(root) {
    if (!io || !root.querySelectorAll) { return; }
    var list = root.querySelectorAll('.metric-number');
    for (var i = 0; list.length > i; i++) { if (!list[i].getAttribute('data-cu')) { io.observe(list[i]); } }
  }
  new win.MutationObserver(function (ms) {
    ms.forEach(function (m) { m.addedNodes.forEach(function (n) { if (n.nodeType === 1) { scan(n); } }); });
  }).observe(doc.body, { childList: true, subtree: true });
  scan(doc);

  try { particles(); } catch (err) { /* decoration only */ }
})"""

def inject_fx() -> None:
    """Run the JS effects layer. Newer Streamlit runs it in the page; older versions use a 0-height iframe."""
    marker = '<div class="cl-fx" aria-hidden="true"></div>'
    try:
        st.html(marker + "<script>" + FX_JS + "(window, document);</script>", unsafe_allow_javascript=True)
    except Exception:
        try:
            import streamlit.components.v1 as components
            components.html("<script>" + FX_JS + "(window.parent, window.parent.document);</script>", height=0)
        except Exception:
            pass

inject_fx()

# GLOSSY SIGNAL-ORB LOGO (lime -> sun -> flare ring, mint/yellow heartbeat)
RAW_SVG = """<svg width="100%" height="100%" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="clRing" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#b6ff3c" />
            <stop offset="0.55" stop-color="#ffd426" />
            <stop offset="1" stop-color="#ff3b72" />
        </linearGradient>
        <radialGradient id="clCore" cx="35%" cy="28%" r="80%">
            <stop offset="0" stop-color="#1f4a2c" />
            <stop offset="0.6" stop-color="#0a1f14" />
            <stop offset="1" stop-color="#030806" />
        </radialGradient>
        <linearGradient id="clPulse" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="#1ff2a0" />
            <stop offset="0.5" stop-color="#e9ff7a" />
            <stop offset="1" stop-color="#ffd426" />
        </linearGradient>
        <filter id="clGlow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
    </defs>
    <circle cx="50" cy="50" r="44" fill="url(#clCore)" stroke="url(#clRing)" stroke-width="4" />
    <circle cx="50" cy="50" r="34" fill="none" stroke="#b6ff3c" stroke-opacity="0.28" stroke-width="1" stroke-dasharray="3 5" />
    <path d="M12 52 H30 L38 30 L50 74 L60 40 L66 52 H88" fill="none" stroke="url(#clPulse)" stroke-width="5"
          stroke-linecap="round" stroke-linejoin="round" filter="url(#clGlow)" />
    <ellipse cx="42" cy="24" rx="20" ry="8" fill="#ffffff" opacity="0.12" />
</svg>"""
B64_LOGO = base64.b64encode(RAW_SVG.encode('utf-8')).decode('utf-8')
ICON_LOGO = f'<img src="data:image/svg+xml;base64,{B64_LOGO}" alt="Logo" style="filter: drop-shadow(0px 6px 14px rgba(182,255,60,0.55));" />'
ICON_UP = '<span class="pill-arrow up" aria-hidden="true"></span>'
ICON_DOWN = '<span class="pill-arrow down" aria-hidden="true"></span>'
ICON_CHEV = '<span class="dq-chev" aria-hidden="true"></span>'

# Session state
if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = 1
if "selected_lang" not in st.session_state:
    st.session_state.selected_lang = "English"
if "selected_diet" not in st.session_state:
    st.session_state.selected_diet = "Vegetarian"
if "analysis_cache" not in st.session_state:
    st.session_state.analysis_cache = {}

TEXTS = {
    "English": {
        "title": "ClarityLab AI",
        "tagline": "Personalized Diagnostic Medical Interpreter",
        "system_status": "Groq LPU Engine Active",
        "lang_modal_title": "Choose Your Language",
        "lang_modal_desc": "Select the language you feel most comfortable reading your medical report analysis in:",
        "lang_modal_btn": "Proceed to Diet Selection →",
        "diet_modal_title": "Choose Dietary Preference",
        "diet_modal_desc": "To give you exact, realistic food solutions from Indian cuisine, please select your diet profile:",
        "diet_modal_btn": "Launch Health Workspace →",
        "radio_lang_label": "Preferred Language",
        "radio_diet_label": "Diet Preference",
        "veg_opt": "Vegetarian",
        "nonveg_opt": "Non-Vegetarian",
        "change_prefs": "Adjust Settings",
        "selected_lang_label": "Language:",
        "diet_profile_label": "Diet Plan:",
        "upload_header": "Upload Medical Lab Report",
        "upload_desc": "Upload your lab test report in PDF or image format (PNG, JPG). The engine reads, evaluates, and explains your biomarkers instantly.",
        "upload_label": "Upload PDF or Image File",
        "summary_title": "Diagnostic Health Overview",
        "missing_title": "Biological Breakdown of Your Biomarkers",
        "recorded_val": "Observed Test Value:",
        "what_happening": "What this means for your body:",
        "food_title": "Evidence-Based Food Suggestions",
        "questions_title": "Important Questions for Your Next Doctor Visit",
        "download_questions": "Save Doctor Questions (.txt)",
        "disclaimer": "Clinical Disclaimer: ClarityLab AI is designed for informational and educational support only. It does not replace medical advice, clinical diagnosis, or prescriptions from a licensed healthcare physician.",
        "pill_normal": "Normal", "pill_high": "High", "pill_low": "Low",
        "stat_total": "Biomarkers", "stat_normal": "In range", "stat_flagged": "Needs attention",
        "range_low": "Low", "range_high": "High",
        "tab_biomarkers": "Biomarkers", "tab_food": "Nutrition", "tab_doctor": "Doctor questions",
        "questions_hint": "Flagged biomarkers are listed first. Tap a biomarker to expand its questions.",
        "no_results": "No medical biomarkers could be extracted from this document. Please ensure the scan is clear.",
        "step": "Step", "general_questions": "General questions",
    },
    "हिंदी": {
        "title": "क्लैरिटीलैब एआई",
        "tagline": "सरल और सटीक मेडिकल रिपोर्ट विश्लेषक",
        "system_status": "ग्रोक एआई डायग्नोस्टिक सक्रिय है",
        "lang_modal_title": "अपनी भाषा चुनें (Select Language)",
        "lang_modal_desc": "अपनी मेडिकल रिपोर्ट को आसानी से समझने के लिए अपनी पसंदीदा भाषा चुनें:",
        "lang_modal_btn": "आहार चयन के लिए आगे बढ़ें →",
        "diet_modal_title": "खान-पान की आदत चुनें (Diet Preference)",
        "diet_modal_desc": "आपको आपकी जीवनशैली के अनुसार सटीक भोजन और परहेज बताने के लिए अपना आहार चुनें:",
        "diet_modal_btn": "हेल्थ डैशबोर्ड खोलें →",
        "radio_lang_label": "पसंदीदा भाषा",
        "radio_diet_label": "आहार विकल्प",
        "veg_opt": "शाकाहारी (Vegetarian)",
        "nonveg_opt": "मांसाहारी (Non-Vegetarian)",
        "change_prefs": "भाषा / आहार बदलें",
        "selected_lang_label": "भाषा:",
        "diet_profile_label": "आहार शैली:",
        "upload_header": "अपनी मेडिकल लैब रिपोर्ट अपलोड करें",
        "upload_desc": "किसी भी फॉर्मेट (PDF या फोटो) में अपनी रिपोर्ट अपलोड करें। ऐप आपकी रिपोर्ट को पढ़कर सरल हिंदी में जानकारी देगा।",
        "upload_label": "PDF या फोटो/इमेज फाइल अपलोड करें",
        "summary_title": "स्वास्थ्य रिपोर्ट का मुख्य सारांश",
        "missing_title": "आपके शरीर के अंगों में क्या हो रहा है",
        "recorded_val": "रिपोर्ट में दर्ज मात्रा:",
        "what_happening": "सरल शब्दों में इसका अर्थ:",
        "food_title": "खाने योग्य पोषक आहार और घरेलू परहेज",
        "questions_title": "अगली बार डॉक्टर से पूछने योग्य जरूरी सवाल",
        "download_questions": "सवालों की सूची डाउनलोड करें (.txt)",
        "disclaimer": "चिकित्सा अस्वीकरण: क्लैरिटीलैब एआई केवल आपकी जानकारी और समझ के लिए है। किसी भी चिकित्सीय निर्णय या दवा बदलने से पहले योग्य डॉक्टर से सलाह जरूर लें।",
        "pill_normal": "सामान्य", "pill_high": "अधिक", "pill_low": "कम",
        "stat_total": "कुल पैरामीटर", "stat_normal": "सामान्य सीमा में", "stat_flagged": "ध्यान दें",
        "range_low": "न्यूनतम", "range_high": "अधिकतम",
        "tab_biomarkers": "बायोमार्कर", "tab_food": "आहार", "tab_doctor": "डॉक्टर से सवाल",
        "questions_hint": "असामान्य पैरामीटर पहले दिखाए गए हैं। सवाल देखने के लिए किसी पैरामीटर पर टैप करें।",
        "no_results": "इस फाइल से कोई मेडिकल पैरामीटर नहीं पढ़ा जा सका। कृपया स्पष्ट स्कैन अपलोड करें।",
        "step": "चरण", "general_questions": "सामान्य सवाल",
    },
    "ગુજરાતી": {
        "title": "ક્લેરિટીલેબ એઆઈ",
        "tagline": "તબીબી લેબ રિપોર્ટનું સરળ વિશ્લેષણ",
        "system_status": "ગ્રોક એઆઈ સિસ્ટમ કાર્યરત છે",
        "lang_modal_title": "તમારી ભાષા પસંદ કરો",
        "lang_modal_desc": "તમારા મેડિકલ રિપોર્ટને સરળતાથી સમજવા માટે તમારી અનુકૂળ ભાષા પસંદ કરો:",
        "lang_modal_btn": "ખોરાક પસંદ કરવા માટે આગળ વધો →",
        "diet_modal_title": "ખોરાકની પસંદગી નક્કી કરો",
        "diet_modal_desc": "તમારા રોજીંદા ભોજન મુજબ યોગ્ય આહાર સૂચવવા માટે પસંદગી કરો:",
        "diet_modal_btn": "હેલ્થ ડેશબોર્ડ શરૂ કરો →",
        "radio_lang_label": "ભાષા",
        "radio_diet_label": "ખોરાકની રીત",
        "veg_opt": "શાકાહારી (Vegetarian)",
        "nonveg_opt": "માસાહારી (Non-Vegetarian)",
        "change_prefs": "સેટિંગ્સ બદલો",
        "selected_lang_label": "પસંદ કરેલી ભાષા:",
        "diet_profile_label": "આહાર પ્રોફાઇલ:",
        "upload_header": "તમારો લેબ રિપોર્ટ અપલોડ કરો",
        "upload_desc": "કોઈ પણ ફોર્મેટમાં (PDF અથવા ફોટો) રિપોર્ટ અપલોડ કરો. રિપોર્ટ વાંચીને તરત સરળ ગુજરાતીમાં સલાહ મળશે.",
        "upload_label": "PDF અથવા ફોટો ફાઇલ અપલોડ કરો",
        "summary_title": "આરોગ્ય રિપોર્ટનો મુખ્ય સારાંશ",
        "missing_title": "તમારા શરીરમાં શું ફેરફાર થઈ રહ્યો છે",
        "recorded_val": "રિપોર્ટમાં નોંધાયેલ પ્રમાણ:",
        "what_happening": "સરળ શબ્દોમાં સમજૂતી:",
        "food_title": "ખાવા યોગ્ય યોગ્ય ખોરાક અને પરહેજ",
        "questions_title": "ડૉક્ટરને પૂછવા માટેના ખાસ પ્રશ્નો",
        "download_questions": "પ્રશ્નોની યાદી સાચવો (.txt)",
        "disclaimer": "તબીબી ડિસ્ક્લેમર: ક્લેરિટીલેબ એઆઈ ફક્ત દર્દીની જાણકારી માટે છે. દવા કે સારવાર બદલતા પહેલાં ફેમિલી ડૉક્ટરની સલાહ લેવી અનિવાર્ય છે.",
        "pill_normal": "સામાન્ય", "pill_high": "વધુ", "pill_low": "ઓછું",
        "stat_total": "કુલ પેરામીટર", "stat_normal": "સામાન્ય મર્યાદામાં", "stat_flagged": "ધ્યાન આપો",
        "range_low": "ન્યૂનતમ", "range_high": "મહત્તમ",
        "tab_biomarkers": "બાયોમાર્કર", "tab_food": "આહાર", "tab_doctor": "ડૉક્ટરને પ્રશ્નો",
        "questions_hint": "અસામાન્ય પેરામીટર પહેલા બતાવ્યા છે. પ્રશ્નો જોવા માટે પેરામીટર પર ટેપ કરો.",
        "no_results": "આ ફાઇલમાંથી કોઈ મેડિકલ પેરામીટર વાંચી શકાયા નહીં. કૃપા કરીને સ્પષ્ટ સ્કેન અપલોડ કરો.",
        "step": "પગલું", "general_questions": "સામાન્ય પ્રશ્નો",
    }
}
L = TEXTS[st.session_state.selected_lang]

# ---------------------------------------------------------
# Helpers shared by the pipeline and the UI
# ---------------------------------------------------------
NUM_RE = r"-?\d+(?:\.\d+)?"

def to_float(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None

# ---------------------------------------------------------
# Document Text Extraction (page-wise, OCR only where needed)
# ---------------------------------------------------------
MODEL = "openai/gpt-oss-120b"
MAX_PAGES = 3             # Drastically reduced to prevent rate limit freezes
CHUNK_CHARS = 6000        # Smaller chunks to fit free-tier limits
OCR_DPI = 100
MAX_SIDE = 1200
MAX_FILE_MB = 10

def _ocr_page(file_bytes, page_no):
    """OCR a single PDF page (1-indexed). Rendering one page at a time keeps memory low."""
    try:
        imgs = pdf2image.convert_from_bytes(
            file_bytes, first_page=page_no, last_page=page_no, dpi=OCR_DPI, fmt="jpeg"
        )
        img = imgs[0]
        w, h = img.size
        if max(w, h) > MAX_SIDE:
            r = MAX_SIDE / max(w, h)
            img = img.resize((int(w * r), int(h * r)), Image.LANCZOS)
        return pytesseract.image_to_string(img)
    except Exception as e:
        print(f"OCR error p{page_no}: {e}")
        return ""

def extract_pages(file_bytes, filename, mime_type):
    if pytesseract is not None and sys.platform.startswith("win"):
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    is_pdf = "pdf" in (mime_type or "").lower() or filename.lower().endswith(".pdf")
    pages = []

    if is_pdf:
        # 1. Native text layer (fast, clean)
        if pypdf is not None:
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                for p in reader.pages[:MAX_PAGES]:
                    pages.append(p.extract_text() or "")
            except Exception:
                pages = []
        # 2. OCR only the pages that have no usable text layer
        if pdf2image is not None and pytesseract is not None:
            if not pages:   # pypdf failed entirely -> OCR blindly
                pages = [""] * MAX_PAGES
            todo = [i for i, t in enumerate(pages) if len(t.strip()) < 40]
            if todo:
                with ThreadPoolExecutor(max_workers=4) as ex:
                    results = list(ex.map(lambda i: _ocr_page(file_bytes, i + 1), todo))
                for i, txt in zip(todo, results):
                    pages[i] = txt
    elif pytesseract is not None:
        try:
            img = Image.open(io.BytesIO(file_bytes))
            w, h = img.size
            if max(w, h) > MAX_SIDE:
                r = MAX_SIDE / max(w, h)
                img = img.resize((int(w * r), int(h * r)), Image.LANCZOS)
            pages = [pytesseract.image_to_string(img)]
        except Exception as e:
            print(f"Image OCR Error: {e}")
    return pages

NOISE = re.compile(
    r"(page \d+|www\.|https?:|@|\bphone\b|\btel\b|\bfax\b|address|disclaimer|nabl|barcode|"
    r"collected|registered|printed|reported on|end of report|lab id|sample id|reg\.? no|"
    r"patient id|referred by|dr\.)", re.I)
RANGE = re.compile(r"\d+(?:\.\d+)?\s*(?:-|–|to)\s*\d+(?:\.\d+)?|[<>≤≥]\s*\d")

def condense(pages):
    """Keep only lines likely to carry results; drop duplicates, paragraphs and boilerplate."""
    seen, out = set(), []
    for text in pages:
        for line in text.splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if len(line) < 3:
                continue
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            has_digit = any(c.isdigit() for c in line)
            if has_digit:
                if NOISE.search(line) and not RANGE.search(line):
                    continue
                out.append(line[:200])
            elif len(line) <= 40:       # likely a test / section name on its own line
                out.append(line)
    return out

def chunk_lines(lines, size=CHUNK_CHARS):
    chunks, cur, n = [], [], 0
    for ln in lines:
        if n + len(ln) > size and cur:
            chunks.append("\n".join(cur))
            cur, n = [], 0
        cur.append(ln)
        n += len(ln) + 1
    if cur:
        chunks.append("\n".join(cur))
    return chunks

# ---------------------------------------------------------
# GROQ LPU ENGINE (multi-stage, token-safe for large files)
# ---------------------------------------------------------
SYS = "You are a clinical lab analysis engine. Respond only with valid JSON."

def call_groq(client, system, user, max_tokens, retries=4):
    """Crash-proof API call that falls back to empty defaults if the AI fails."""
    for attempt in range(retries):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system + " Output ONLY strict JSON. No markdown. No trailing commas."},
                    {"role": "user", "content": user}
                ],
                temperature=0.0, # 0.0 prevents typos and creative formatting
                max_tokens=max_tokens,
            )
            
            content = r.choices[0].message.content or ""
            if not content.strip():
                print(f"[call_groq] empty reply, finish_reason={r.choices[0].finish_reason}")
            
            # Isolate the JSON block
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                clean_json = content[start_idx:end_idx+1]
                
                # Safely remove trailing commas (the most common AI formatting mistake)
                clean_json = re.sub(r',\s*([}\]])', r'\1', clean_json)
                
                try:
                    return json.loads(clean_json)
                except json.JSONDecodeError:
                    # If the AI cut off mid-sentence due to length, try closing the brackets
                    try:
                        return json.loads(clean_json + ']}')
                    except:
                        try:
                            return json.loads(clean_json + '}')
                        except:
                            pass # Move to the next retry
                            
        except Exception as e:
            print(f"[call_groq] attempt {attempt + 1}/{retries} failed: {e}")
            msg = str(e).lower()
            if "429" in msg or "rate" in msg or "413" in msg:
                time.sleep(3)
                continue
            time.sleep(1)
            
    print("[call_groq] giving up, returning empty result")
    # THE HARD FAIL-SAFE: If it fails all retries, return an empty structure so the UI NEVER crashes.
    return {"r": [], "items": [], "summary": "Analysis completed, but some data was unreadable."}
def _status(item):
    """Compute high/low/normal in Python from value + reference range (zero tokens)."""
    v, lo, hi = to_float(item.get("v")), to_float(item.get("lo")), to_float(item.get("hi"))
    if v is not None and (lo is not None or hi is not None):
        if hi is not None and v > hi:
            return "high"
        if lo is not None and v < lo:
            return "low"
        return "normal"
    return {"H": "high", "L": "low"}.get(str(item.get("f", "N")).upper(), "normal")

def analyze_report_with_groq(file_bytes, filename, mime_type, target_lang, target_diet, api_key):
    try:
        if Groq is None:
            return None, "groq library not installed. Run: pip install groq"
        if not api_key or not api_key.strip():
            return None, "GROQ_API_KEY not found. Add it to .streamlit/secrets.toml or set it as an environment variable."
        if len(file_bytes) > MAX_FILE_MB * 1024 * 1024:
            return None, f"File is larger than {MAX_FILE_MB} MB. Please use a lower-resolution scan."

        pages = extract_pages(file_bytes, filename, mime_type)
        lines = condense(pages)
        print(f"[analyze] pages={len(pages)} text_lines={len(lines)}")
        if not lines:
            return None, "Could not extract text from document. Please ensure it is a clear scan."

        client = Groq(api_key=api_key.strip())

        # ---- Stage 1: compact extraction, chunk by chunk ----
        found, seen = [], set()
        for chunk in chunk_lines(lines):
            prompt = f"""Extract every lab test result from this report text.
Return JSON: {{"r":[{{"n":"test name (English)","c":"category","v":number or null,"u":"unit","lo":number or null,"hi":number or null,"f":"H"|"L"|"N"}}]}}
"f" = flag printed in the report (H/L/N). For ranges like "<200" use hi=200, lo=null.
Ignore IDs, addresses, doctor names, notes. Never invent values.

TEXT:
{chunk}"""
            data = call_groq(client, SYS, prompt, max_tokens=3000)
            for it in data.get("r", []):
                key = (str(it.get("n", "")).lower(), str(it.get("v")))
                if it.get("n") and key not in seen:
                    seen.add(key)
                    found.append(it)

        print(f"[analyze] biomarkers found={len(found)}")
        if not found:
            return None, None   # UI shows the "no results" message

        for it in found:
            it["code"] = _status(it)

        # ---- Stage 2: explanations only for abnormal biomarkers ----
        abnormal = [i for i, it in enumerate(found) if it["code"] != "normal"]
        batch_size = 8 if target_lang == "English" else 4   # Indic scripts cost more tokens
        for s in range(0, len(abnormal), batch_size):
            idxs = abnormal[s:s + batch_size]
            items = [{"i": i, "n": found[i]["n"], "v": found[i].get("v"),
                      "u": found[i].get("u"), "status": found[i]["code"]} for i in idxs]
            prompt = f"""Language for ALL text values: {target_lang}. Diet: {target_diet} (Indian cuisine).
For each abnormal lab result below return JSON:
{{"items":[{{"i":<same index>,"e":"1-2 sentence simple explanation","f":"3-4 specific Indian {target_diet} food suggestions","q":["question 1","question 2"]}}]}}

RESULTS:
{json.dumps(items, ensure_ascii=False)}"""
            out = call_groq(client, SYS, prompt,
                            max_tokens=2500 if target_lang == "English" else 4000)
            for e in out.get("items", []):
                try:
                    j = int(e.get("i"))
                except (TypeError, ValueError):
                    continue
                if 0 <= j < len(found):
                    found[j]["e"] = e.get("e", "")
                    found[j]["fd"] = e.get("f", "")
                    found[j]["q"] = e.get("q", [])

        # ---- Summary (tiny call) ----
        brief = [f'{it["n"]}: {it.get("v")} {it.get("u", "")} ({it["code"]})' for it in found]
        sm = call_groq(
            client, SYS,
            f'Write a 2-3 sentence overview in {target_lang} of these lab results. '
            f'Return {{"summary":"..."}}.\n' + "\n".join(brief[:80]),
            max_tokens=600,
        )

        params = []
        for it in found:
            v, u = it.get("v"), it.get("u") or ""
            params.append({
                "name": it["n"], "category": it.get("c", ""),
                "value": f"{v} {u}".strip() if v is not None else "",
                "numeric_value": v, "unit": u,
                "ref_low": it.get("lo"), "ref_high": it.get("hi"),
                "status_code": it["code"],
                "explanation": it.get("e", ""),
                "food_remedies": it.get("fd", ""),
                "questions_for_doctor": it.get("q", []),
            })
        return {"summary": sm.get("summary", ""), "parameters": params}, None

    except Exception as e:
        return None, f"Groq Execution Error: {e}"

# ---------------------------------------------------------
# Normalization & UI Builders
# ---------------------------------------------------------
def status_code_of(param) -> str:
    code = str(param.get("status_code", "")).strip().lower()
    if code in ("normal", "high", "low"):
        return code
    text = str(param.get("status", "")).lower()
    if any(w in text for w in ("low", "कम", "ઓછું", "below")):
        return "low"
    if any(w in text for w in ("high", "अधिक", "વધુ", "above", "elevated")):
        return "high"
    return "normal"

def normalise(param) -> dict:
    raw_value = str(param.get("value", "") or "")
    value = to_float(param.get("numeric_value"))
    low = to_float(param.get("ref_low"))
    high = to_float(param.get("ref_high"))
    unit = str(param.get("unit", "") or "")
    
    if value is None:
        m = re.search(NUM_RE, raw_value)
        value = float(m.group()) if m else None
        
    if low is None and high is None:
        ref_part = raw_value.split("(", 1)[1] if "(" in raw_value else ""
        rng = re.search(rf"({NUM_RE})\s*(?:-|–|to)\s*({NUM_RE})", ref_part)
        if rng:
            low, high = float(rng.group(1)), float(rng.group(2))
            
    # Safely handle Questions if the AI returns a string, list, or null
    questions = param.get("questions_for_doctor") or []
    if isinstance(questions, str):
        questions = [q.strip() for q in questions.split("\n") if q.strip()]
        
    # Safely handle Food if the AI returns a list, string, or null
    food_data = param.get("food", "") or param.get("food_remedies", "")
    if isinstance(food_data, list):
        # Convert list into a single bulleted string
        food_data = "\n• ".join(str(x) for x in food_data)
    elif food_data is None:
        food_data = ""
    else:
        food_data = str(food_data)
        
    return {
        "name": param.get("name", "Biomarker"),
        "category": param.get("category", ""),
        "raw_value": raw_value,
        "value": value,
        "unit": unit,
        "low": low,
        "high": high,
        "code": status_code_of(param),
        "explanation": param.get("explanation", ""),
        "food": food_data,
        "questions": questions if isinstance(questions, list) else [],
    }

def fmt_num(n: float) -> str:
    return f"{n:g}" if abs(n) < 1e6 else f"{n:.3g}"

def status_pill(code: str) -> str:
    icon = ICON_UP if code == "high" else ICON_DOWN if code == "low" else ""
    label = esc(L[f"pill_{code}"])
    return (
        f'<span class="pill pill-{code}" role="status" aria-label="{label}">'
        f'<span class="pill-dot" aria-hidden="true"></span>{label}{icon}</span>'
    )

def range_bar(b: dict) -> str:
    value, low, high = b["value"], b["low"], b["high"]
    if value is None or high is None:
        return ""
    low = low if low is not None else 0.0
    span = (high - low) or max(abs(high), 1.0)
    lo_edge = max(0.0, low - span * 0.5) if low >= 0 else low - span * 0.5
    hi_edge = high + span * 0.5
    def pct(n):
        return min(100.0, max(0.0, (n - lo_edge) / (hi_edge - lo_edge) * 100))
    return f"""
    <div class="range" aria-hidden="true" style="--lo:{pct(low):.1f}%;--hi:{pct(high):.1f}%">
        <div class="range-track">
            <div class="range-safe" style="left:{pct(low):.1f}%;width:{pct(high) - pct(low):.1f}%"></div>
            <div class="range-marker" style="left:{pct(value):.1f}%"><span class="range-tip">{fmt_num(value)}</span></div>
        </div>
        <div class="range-labels"><span>{esc(L['range_low'])} {fmt_num(low)}</span><span>{esc(L['range_high'])} {fmt_num(high)}</span></div>
    </div>
    """

def metric_card(b: dict, index: int) -> str:
    state_cls = {"high": "is-flagged", "low": "is-low"}.get(b["code"], "")
    flag_bar = '<span class="flag-bar" aria-hidden="true"></span>' if b["code"] != "normal" else ""
    category = f'<p class="metric-cat">{esc(b["category"])}</p>' if b["category"] else ""
    if b["value"] is not None:
        value_html = f'<span class="metric-number">{fmt_num(b["value"])}</span><span class="metric-unit">{esc(b["unit"])}</span>'
    else:
        value_html = f'<span class="metric-raw">{esc(b["raw_value"])}</span>'
    explain = ""
    if b["explanation"]:
        explain = f'<p class="metric-explain"><strong>{esc(L["what_happening"])}</strong>{esc(b["explanation"])}</p>'
    return f"""
    <article class="metric-card {state_cls}" style="animation-delay:{index * 90}ms">
        {flag_bar}
        <header class="metric-head">
            <div>{category}<h3 class="metric-name">{esc(b["name"])}</h3></div>
            {status_pill(b["code"])}
        </header>
        <p class="metric-value">{value_html}</p>
        {range_bar(b)}
        {explain}
    </article>
    """

def summary_panel(summary: str, biomarkers: list) -> str:
    total = len(biomarkers)
    flagged = [b for b in biomarkers if b["code"] != "normal"]
    normal = total - len(flagged)
    pct_normal = round(normal / total * 100) if total else 0
    tags = "".join(f'<span class="cl-flag-tag">{esc(b["name"])}</span>' for b in flagged)
    tag_row = f'<div class="cl-flag-list">{tags}</div>' if tags else ""
    groups = {}
    for b in biomarkers:
        if b["category"]:
            groups.setdefault(b["category"], []).append(b["code"])
    systems = "".join(
        f'<div class="cl-sys"><div class="cl-sys-head"><span class="cl-sys-name">{esc(cat)}</span>'
        f'<span class="cl-sys-n">{codes.count("normal")}/{len(codes)}</span></div>'
        f'<div class="cl-seg-row">'
        + "".join(f'<span class="cl-seg cl-seg-{c}" style="animation-delay:{0.35 + k * 0.06:.2f}s"></span>' for k, c in enumerate(codes))
        + '</div></div>'
        for cat, codes in groups.items()
    )
    systems_row = f'<div class="cl-systems">{systems}</div>' if systems else ""
    return f"""
    <section class="cl-summary">
        <div class="cl-sum-main">
            <div class="cl-sum-copy">
                <p class="cl-eyebrow">{esc(L['summary_title'])}</p>
                <p class="cl-summary-text">{esc(summary)}</p>
            </div>
            <div class="cl-ring" style="--pct:{pct_normal}" role="img" aria-label="{esc(L['stat_normal'])}: {pct_normal}%">
                <span class="cl-ring-val cl-count" style="--n:{pct_normal}" aria-hidden="true"></span>
                <span class="cl-ring-label">{esc(L['stat_normal'])}</span>
            </div>
        </div>
        <div class="cl-stats">
            <div class="cl-stat cl-stat-total" role="group" aria-label="{esc(L['stat_total'])}: {total}"><span class="cl-stat-label">{esc(L['stat_total'])}</span><span class="cl-stat-value cl-count" style="--n:{total}" aria-hidden="true"></span></div>
            <div class="cl-stat cl-stat-normal" role="group" aria-label="{esc(L['stat_normal'])}: {normal}"><span class="cl-stat-label">{esc(L['stat_normal'])}</span><span class="cl-stat-value cl-count" style="--n:{normal}" aria-hidden="true"></span></div>
            <div class="cl-stat cl-stat-flagged" role="group" aria-label="{esc(L['stat_flagged'])}: {len(flagged)}"><span class="cl-stat-label">{esc(L['stat_flagged'])}</span><span class="cl-stat-value cl-count" style="--n:{len(flagged)}" aria-hidden="true"></span></div>
        </div>
        {systems_row}
        {tag_row}
    </section>
    """

def question_accordion(title: str, questions: list, code, is_open: bool, index: int) -> str:
    items = "".join(f"<li>{esc(q)}</li>" for q in questions)
    pill = status_pill(code) if code else ""
    return f"""
    <details class="dq" {'open' if is_open else ''} style="animation-delay:{index * 80}ms">
        <summary>
            <span class="dq-left"><span class="dq-count">{len(questions)}</span><span class="dq-name">{esc(title)}</span></span>
            <span class="dq-right">{pill}{ICON_CHEV}</span>
        </summary>
        <div class="dq-body"><ol>{items}</ol></div>
    </details>
    """

# ---------------------------------------------------------
# STEP 1: ONBOARDING MODAL 1 - LANGUAGE
# ---------------------------------------------------------
LANG_OPTIONS = ["English", "हिंदी", "ગુજરાતી"]
if st.session_state.onboarding_step == 1:
    _, center, _ = st.columns([1, 1.8, 1])
    with center:
        render_html(f"""
        <div class="ob-card">
            <div class="cl-logo">{ICON_LOGO}</div>
            <span class="ob-step">{esc(L['step'])} 1 / 2</span>
            <h2 class="ob-title">{esc(L['lang_modal_title'])}</h2>
            <p class="ob-desc">{esc(L['lang_modal_desc'])}</p>
        </div>
        """)
        selected_l = st.radio(
            L["radio_lang_label"],
            LANG_OPTIONS,
            index=LANG_OPTIONS.index(st.session_state.selected_lang),
            label_visibility="collapsed",
        )
        if st.button(L["lang_modal_btn"], use_container_width=True):
            st.session_state.selected_lang = selected_l
            st.session_state.onboarding_step = 2
            st.rerun()

# ---------------------------------------------------------
# STEP 2: ONBOARDING MODAL 2 - DIET
# ---------------------------------------------------------
elif st.session_state.onboarding_step == 2:
    _, center, _ = st.columns([1, 1.8, 1])
    with center:
        render_html(f"""
        <div class="ob-card">
            <div class="cl-logo">{ICON_LOGO}</div>
            <span class="ob-step">{esc(L['step'])} 2 / 2</span>
            <h2 class="ob-title">{esc(L['diet_modal_title'])}</h2>
            <p class="ob-desc">{esc(L['diet_modal_desc'])}</p>
        </div>
        """)
        selected_d = st.radio(
            L["radio_diet_label"],
            [L["veg_opt"], L["nonveg_opt"]],
            index=0 if st.session_state.selected_diet == "Vegetarian" else 1,
            label_visibility="collapsed",
        )
        if st.button(L["diet_modal_btn"], use_container_width=True):
            st.session_state.selected_diet = "Vegetarian" if selected_d == L["veg_opt"] else "Non-Vegetarian"
            st.session_state.onboarding_step = 3
            st.rerun()

# ---------------------------------------------------------
# STEP 3: MAIN MEDICAL DASHBOARD
# ---------------------------------------------------------
else:
    head_col, action_col = st.columns([4, 1], vertical_alignment="center")
    with head_col:
        render_html(f"""
        <header class="cl-header">
            <div class="cl-brand">
                <div class="cl-logo">{ICON_LOGO}</div>
                <div>
                    <h1 class="cl-title">{esc(L['title'])}</h1>
                    <p class="cl-tagline">{esc(L['tagline'])}</p>
                </div>
            </div>
            <span class="cl-chip"><span class="cl-chip-dot" aria-hidden="true"></span>{esc(L['system_status'])}</span>
        </header>
        """)
    with action_col:
        if st.button(L["change_prefs"], key="change_prefs", use_container_width=True):
            st.session_state.onboarding_step = 1
            st.rerun()

    translated_diet = L["veg_opt"] if st.session_state.selected_diet == "Vegetarian" else L["nonveg_opt"]
    render_html(f"""
    <div class="cl-prefs">
        <span>{esc(L['selected_lang_label'])} <strong>{esc(st.session_state.selected_lang)}</strong></span>
        <span>{esc(L['diet_profile_label'])} <strong>{esc(translated_diet)}</strong></span>
    </div>
    """)

    # Secure Automatic Groq Key Pipeline (Reads from secrets.toml or environment)
    groq_api_key = ""
    try:
        groq_api_key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        pass
    groq_api_key = groq_api_key or os.environ.get("GROQ_API_KEY", "")

    render_html(f"""
    <div style="margin-top:24px">
        <p class="cl-eyebrow">01</p>
        <h2 class="cl-h2">{esc(L['upload_header'])}</h2>
        <p class="cl-sub">{esc(L['upload_desc'])}</p>
    </div>
    """)

    uploaded_file = st.file_uploader(L["upload_label"], type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

    parsed_report_data = None
    error_notice = None

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        mime_type = uploaded_file.type or "application/pdf"

        if uploaded_file.size > 6 * 1024 * 1024:
            st.info("Large file detected. It will be processed in chunks, so this may take a minute.")

        cache_key = (
            hashlib.sha256(file_bytes).hexdigest(),
            st.session_state.selected_lang,
            st.session_state.selected_diet,
        )
        parsed_report_data = st.session_state.analysis_cache.get(cache_key)

        if parsed_report_data is None:
            with st.spinner("Decoding report structures & extracting biomarker matrix..."):
                parsed_report_data, error_notice = analyze_report_with_groq(
                    file_bytes, uploaded_file.name, mime_type,
                    st.session_state.selected_lang, st.session_state.selected_diet,
                    groq_api_key
                )
            if parsed_report_data:
                st.session_state.analysis_cache[cache_key] = parsed_report_data

        if error_notice and not parsed_report_data:
            st.error(error_notice)
        elif not parsed_report_data:
            render_html(f'<div class="cl-empty">{esc(L["no_results"])}</div>')

    # -----------------------------------------------------
    # Render Diagnostic Results
    # -----------------------------------------------------
    if parsed_report_data:
        biomarkers = [normalise(p) for p in parsed_report_data.get("parameters", [])]
        order = {"high": 0, "low": 1, "normal": 2}
        biomarkers_sorted = sorted(biomarkers, key=lambda b: order[b["code"]])

        render_html(summary_panel(parsed_report_data.get("summary", ""), biomarkers))

        tab_bio, tab_food, tab_doc = st.tabs([
            f"{L['tab_biomarkers']} ({len(biomarkers)})",
            L["tab_food"],
            L["tab_doctor"],
        ])

        with tab_bio:
            cards = "".join(metric_card(b, i) for i, b in enumerate(biomarkers_sorted))
            render_html(f"""
            <section class="sec-bio" aria-label="{esc(L['missing_title'])}">
                <p class="cl-eyebrow">02</p>
                <h2 class="cl-h2">{esc(L['missing_title'])}</h2>
                <div class="metric-grid">{cards}</div>
            </section>
            """)

        with tab_food:
            food_cards = "".join(
                f"""
                <article class="food-card" style="animation-delay:{i * 90}ms">
                    <header class="food-head"><h3 class="food-title">{esc(b['name'])}</h3>{status_pill(b['code'])}</header>
                    <div class="food-body">{b['food'].replace('-', '•')}</div>
                </article>
                """
                for i, b in enumerate(biomarkers_sorted) if b["food"]
            )
            render_html(f"""
            <section class="sec-food" aria-label="{esc(L['food_title'])}">
                <p class="cl-eyebrow">03</p>
                <h2 class="cl-h2">{esc(L['food_title'])}</h2>
                <div class="metric-grid">{food_cards}</div>
            </section>
            """)

        with tab_doc:
            groups = [(b["name"], b["questions"], b["code"]) for b in biomarkers_sorted if b["questions"]]
            top_level = parsed_report_data.get("questions") or []
            if not groups and top_level:
                groups = [(L["general_questions"], top_level, None)]
            if groups:
                accordions = "".join(
                    question_accordion(title, qs, code, is_open=(i == 0), index=i)
                    for i, (title, qs, code) in enumerate(groups)
                )
                render_html(f"""
                <section class="sec-doc" aria-label="{esc(L['questions_title'])}">
                    <p class="cl-eyebrow">04</p>
                    <h2 class="cl-h2">{esc(L['questions_title'])}</h2>
                    <p class="cl-tagline" style="margin-bottom:26px;">{esc(L['questions_hint'])}</p>
                    <div class="dq-list">{accordions}</div>
                </section>
                """)
                q_text = "\n\n".join(
                    f"{title}\n" + "\n".join(f"  {n}. {q}" for n, q in enumerate(qs, 1))
                    for title, qs, _ in groups
                )
                st.download_button(
                    label=L["download_questions"],
                    data=q_text,
                    file_name=f"doctor_questions_{st.session_state.selected_lang.lower()}.txt",
                    mime="text/plain",
                )

    render_html(f'<footer class="cl-footer">{esc(L["disclaimer"])}</footer>')
