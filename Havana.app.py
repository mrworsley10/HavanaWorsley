import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import urllib3

# --- PAGE SETUP ---
st.set_page_config(page_title="Havana's PB Tracker", page_icon="🌟", layout="centered")

# --- CUSTOM CSS FOR A BEAUTIFUL MOBILE UI ---
st.markdown("""
<style>
    .stApp { background-color: #0f172a; color: #f8fafc; }
    .header-box { background: linear-gradient(135deg, #3b82f6 0%, #1e293b 100%); padding: 25px; border-radius: 15px; text-align: center; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border-bottom: 4px solid #facc15; }
    .header-title { font-size: 2.2rem; font-weight: 900; color: #ffffff; margin: 0; line-height: 1.2; }
    .header-sub { font-size: 1rem; color: #cbd5e1; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
    
    /* Spotlight CSS */
    .spotlight-box { background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%); padding: 20px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border-left: 5px solid #fde047; }
    .spotlight-title { font-size: 1.4rem; font-weight: 900; color: #ffffff; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;}
    .spotlight-item { background: rgba(0,0,0,0.25); padding: 12px; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border: 1px solid rgba(255,255,255,0.1);}
    .spotlight-evt { font-weight: 800; color: #fff; font-size: 1.1rem; }
    .spotlight-gap { color: #fef08a; font-weight: 700; font-size: 0.95rem; text-align: right;}

    .pb-card { background-color: #1e293b; border-radius: 12px; padding: 18px; margin-bottom: 16px; border-left: 5px solid #3b82f6; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); }
    .pb-card.qualified-county { border-left-color: #facc15; }
    .pb-card.qualified-regional { border-left-color: #4ade80; }
    .evt-title { font-size: 1.2rem; font-weight: 800; color: #f8fafc; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 8px;}
    .badge { background: #0f172a; padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; color: #94a3b8; font-weight: bold; }
    .badge.achieved { background: #166534; color: #4ade80; }
    .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; text-align: center; margin-top: 10px;}
    .box { background: #0f172a; padding: 10px; border-radius: 8px; }
    .box-label { font-size: 0.7rem; color: #64748b; text-transform: uppercase; font-weight: 700; margin-bottom: 4px;}
    .box-val { font-size: 1.2rem; font-weight: 900; color: #ffffff;}
    .box-val.time-pb { color: #3b82f6; }
    .gap-green { color: #4ade80; font-size: 0.85rem; font-weight: bold; margin-top: 4px;}
    .gap-red { color: #f87171; font-size: 0.85rem; font-weight: bold; margin-top: 4px;}
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def extract_standard_event(event_str):
    t = str(event_str).lower()
    t = t.replace('breaststroke', 'breast').replace('breaststrok', 'breast')
    t = t.replace('freestyle', 'free').replace('backstroke', 'back').replace('butterfly', 'fly')
    t = t.replace('individual medley', 'im').replace('ind medley', 'im').replace('ind. medley', 'im')
    t = t.replace('individual', 'im')
    
    m = re.search(r'(\d+)\s*m?\s*([a-z]+)', t)
    if m:
        dist = m.group(1)
        stroke = m.group(2).capitalize()
        if stroke.lower() == 'im': stroke = "IM"
        return f"{dist}m {stroke}"
    return str(event_str).title()

def time_to_seconds(t_str):
    if not t_str or pd.isna(t_str) or str(t_str).strip().upper() in ["N/A", "NT", ""]: return None
    t_str = re.sub(r'[^\d:\.]', '', str(t_str).strip())
    if not t_str: return None
    try:
        parts = re.split(r'[:\.]', t_str)
        if len(parts) == 3: return float(parts[0]) * 60 + float(parts[1]) + float(parts[2].ljust(2,'0')[:2]) / 100.0
        elif len(parts) == 2:
            ms_val = parts[1].ljust(2,'0')[:2]
            if ":" in t_str or len(parts[0]) < 3: return float(parts[0]) * 60 + float(parts[1]) if ":" in t_str else float(parts[0]) + float(ms_val) / 100.0
            else: return int(parts[0][:-2]) * 60 + int(parts[0][-2:]) + float(ms_val) / 100.0
        elif len(parts) == 1: return float(parts[0])
    except: return None
    return None

def seconds_to_time(sec):
    return "N/A" if sec is None or sec < 0 else (f"{int(sec // 60)}:{sec % 60:05.2f}" if sec >= 60 else f"{sec % 60:05.2f}")

# --- WEB SCRAPER ---
@st.cache_data(ttl=3600) 
def scrape_swim_england_pbs(url):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
    
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        all_swims = []
        for table in soup.find_all('table'):
            sc_idx = lc_idx = -1
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if not cells: continue
                if sc_idx == -1:
                    for i, c in enumerate(cells):
                        if "short course pb" in c.lower(): sc_idx = i
                        elif "long course pb" in c.lower(): lc_idx = i
                    continue 
                if sc_idx == -1 or lc_idx == -1: break
                
                event_name = cells[0]
                if not re.search(r'\d+m\s+[A-Za-z]+', event_name, re.IGNORECASE): continue
                clean_evt = extract_standard_event(event_name)
                if not clean_evt: continue
                
                if len(cells) > max(sc_idx, lc_idx):
                    sc_time, lc_time = cells[sc_idx], cells[lc_idx]
                    if sc_time and sc_time != '.': all_swims.append({"Event": clean_evt, "Course": "25m", "Time": sc_time})
                    if lc_time and lc_time != '.': all_swims.append({"Event": clean_evt, "Course": "50m", "Time": lc_time})
            if sc_idx != -1: break
        return pd.DataFrame(all_swims)
    except Exception as e:
        st.error(f"Failed to fetch PB times: {e}")
        return pd.DataFrame()

# --- APP UI & LOGIC ---

URL = "https://www.swimmingresults.org/biogs/biogs_details.php?tiref=1790307"

st.markdown("""
<div class="header-box">
    <div class="header-title">🌟 Havana's Dashboard</div>
    <div class="header-sub">Official PB Tracker & Targets</div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1: current_age = st.number_input("Select Current Racing Age", min_value=9, max_value=18, value=11)
with col2: course_filter = st.selectbox("Pool Size", ["25m", "50m"])

try:
    target_df = pd.read_csv("target_times.csv")
    cols = {str(c).strip().lower(): c for c in target_df.columns}
    rename_map = {}
    for c_lower, c_orig in cols.items():
        if 'county' in c_lower: rename_map[c_orig] = 'county_time'
        elif 'region' in c_lower: rename_map[c_orig] = 'regional_time'
        elif 'event' in c_lower: rename_map[c_orig] = 'event'
        elif 'age' in c_lower: rename_map[c_orig] = 'age'
        elif 'gender' in c_lower or 'sex' in c_lower: rename_map[c_orig] = 'gender'
    target_df.rename(columns=rename_map, inplace=True)
    if "event" in target_df.columns: target_df["event"] = target_df["event"].apply(extract_standard_event)
    has_targets = True
except:
    has_targets = False
    st.warning("⚠️ Could not find 'target_times.csv'. Please make sure it's uploaded.")

with st.spinner("Fetching official times from Swim England..."):
    pb_df = scrape_swim_england_pbs(URL)

if pb_df.empty:
    st.info("No personal best times found or the Swim England website is currently unavailable.")
    st.stop()

view_df = pb_df[pb_df["Course"] == course_filter].copy()

if view_df.empty:
    st.info(f"No PB times found for the {course_filter} pool.")
    st.stop()

# --- PRE-PROCESS DATA FOR SPOTLIGHT ---
close_targets = []
dashboard_cards = []

for _, row in view_df.iterrows():
    evt, pb_str = row["Event"], row["Time"]
    pb_sec = time_to_seconds(pb_str)
    
    c_str, r_str, c_sec, r_sec = "N/A", "N/A", None, None
    status_class, status_badge = "", "Keep Pushing!"
    
    if has_targets and "gender" in target_df.columns and "age" in target_df.columns and "event" in target_df.columns:
        match = target_df[(target_df["gender"].str.upper() == "F") & (target_df["age"] == current_age) & (target_df["event"].str.lower() == evt.lower())]
        
        if not match.empty:
            c_val, r_val = match.iloc[0].get("county_time"), match.iloc[0].get("regional_time")
            c_str = str(c_val) if pd.notna(c_val) and str(c_val).lower() != "nan" else "N/A"
            r_str = str(r_val) if pd.notna(r_val) and str(r_val).lower() != "nan" else "N/A"
            c_sec, r_sec = time_to_seconds(c_str), time_to_seconds(r_str)
            
            # Check qualifications
            if r_sec and pb_sec and pb_sec <= r_sec: status_class, status_badge = "qualified-regional", "🏆 REGIONAL QUALIFIER"
            elif c_sec and pb_sec and pb_sec <= c_sec: status_class, status_badge = "qualified-county", "🌟 COUNTY QUALIFIER"
            
            # Track missed targets for Spotlight
            if c_sec and pb_sec > c_sec: 
                close_targets.append({"Event": evt, "Level": "County", "Gap": pb_sec - c_sec, "Target": c_str})
            if r_sec and pb_sec > r_sec: 
                close_targets.append({"Event": evt, "Level": "Regional", "Gap": pb_sec - r_sec, "Target": r_str})

    def get_gap_html(pb, target):
        if not pb or not target: return ""
        diff = pb - target
        if diff <= 0: return f"<div class='gap-green'>✅ Qualified!</div>"
        return f"<div class='gap-red'>Drop {seconds_to_time(diff)}</div>"

    c_gap, r_gap = get_gap_html(pb_sec, c_sec), get_gap_html(pb_sec, r_sec)
    badge_html = f"<span class='badge {'achieved' if status_class else ''}'>{status_badge}</span>"

    card_html = f"""<div class="pb-card {status_class}">
<div class="evt-title"><span>{evt}</span>{badge_html}</div>
<div class="grid">
<div class="box"><div class="box-label">Current PB</div><div class="box-val time-pb">{pb_str}</div></div>
<div class="box"><div class="box-label">County Target</div><div class="box-val">{c_str}</div>{c_gap}</div>
<div class="box"><div class="box-label">Regional Target</div><div class="box-val">{r_str}</div>{r_gap}</div>
</div></div>"""
    dashboard_cards.append(card_html)

# --- RENDER SPOTLIGHT ---
if close_targets:
    # Sort by the smallest gap (closest to hitting the target)
    close_targets.sort(key=lambda x: x["Gap"])
    top_3 = close_targets[:3]
    
    spotlight_html = """<div class="spotlight-box"><div class="spotlight-title">🔥 So Close! Next Best Targets</div>"""
    for t in top_3:
        spotlight_html += f"""
        <div class="spotlight-item">
            <div class="spotlight-evt">{t['Event']} ({t['Level']})</div>
            <div class="spotlight-gap">Drop {seconds_to_time(t['Gap'])} to hit {t['Target']}</div>
        </div>"""
    spotlight_html += "</div>"
    st.markdown(spotlight_html, unsafe_allow_html=True)

# --- RENDER DASHBOARD CARDS ---
for card in dashboard_cards:
    st.markdown(card, unsafe_allow_html=True)