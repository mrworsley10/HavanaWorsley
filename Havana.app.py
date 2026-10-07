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
    m = re.search(r'(\d+m\s+[A-Za-z]+(?:\s+IM)?)', str(event_str), re.IGNORECASE)
    if m: return m.group(1).title().replace('Breaststroke', 'Breast').replace('Breaststrok', 'Breast').replace('Freestyle', 'Free').replace('Backstroke', 'Back').replace('Butterfly', 'Fly').replace('Ind. Medley', 'IM').replace('Ind Medley', 'IM').replace('M ', 'm ').replace(' Im', ' IM').strip()
    return ""

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

# --- WEB SCRAPER FOR SWIM ENGLAND BIOGS SUMMARY TABLE ---
@st.cache_data(ttl=3600) # Caches the data for 1 hour to keep it fast
def scrape_swim_england_pbs(url):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        all_swims = []
        
        for table in soup.find_all('table'):
            sc_idx = -1
            lc_idx = -1
            
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if not cells: continue
                
                if sc_idx == -1:
                    for i, c in enumerate(cells):
                        c_lower = c.lower()
                        if "short course pb" in c_lower: sc_idx = i
                        elif "long course pb" in c_lower: lc_idx = i
                    continue 
                
                if sc_idx == -1 or lc_idx == -1: break
                
                event_name = cells[0]
                if not re.search(r'\d+m\s+[A-Za-z]+', event_name, re.IGNORECASE):
                    continue
                    
                clean_evt = extract_standard_event(event_name)
                if not clean_evt: continue
                
                if len(cells) > max(sc_idx, lc_idx):
                    sc_time = cells[sc_idx]
                    lc_time = cells[lc_idx]
                    
                    if sc_time and sc_time != '.':
                        all_swims.append({"Event": clean_evt, "Course": "25m", "Time": sc_time})
                        
                    if lc_time and lc_time != '.':
                        all_swims.append({"Event": clean_evt, "Course": "50m", "Time": lc_time})
            
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

# 1. User Controls
col1, col2 = st.columns(2)
with col1:
    current_age = st.number_input("Select Current Racing Age", min_value=9, max_value=18, value=10)
with col2:
    course_filter = st.selectbox("Pool Size", ["25m", "50m"])

# Load Target Times
try:
    target_df = pd.read_csv("target_times.csv")
    target_df.rename(columns={"gender": "Gender", "age": "Age", "event": "Event", "county_time": "County_Time", "regional_time": "Regional_Time"}, inplace=True)
    has_targets = True
except:
    has_targets = False
    st.warning("⚠️ Could not find 'target_times.csv'. Please make sure it's uploaded to your Streamlit app.")

# 2. Fetch and Display PBs
with st.spinner("Fetching official times from Swim England..."):
    pb_df = scrape_swim_england_pbs(URL)

if pb_df.empty:
    st.info("No personal best times found or the Swim England website is currently unavailable.")
    st.stop()

# Filter by selected pool size
view_df = pb_df[pb_df["Course"] == course_filter].copy()

if view_df.empty:
    st.info(f"No PB times found for the {course_filter} pool.")
    st.stop()

# 3. Render the Dashboard
for _, row in view_df.iterrows():
    evt = row["Event"]
    pb_str = row["Time"]
    pb_sec = time_to_seconds(pb_str)
    
    c_str, r_str = "N/A", "N/A"
    c_sec, r_sec = None, None
    status_class = ""
    status_badge = "Keep Pushing!"
    
    if has_targets:
        match = target_df[(target_df["Gender"] == "F") & (target_df["Age"] == current_age) & (target_df["Event"].str.lower() == evt.lower())]
        if not match.empty:
            c_val = match.iloc[0].get("County_Time")
            r_val = match.iloc[0].get("Regional_Time")
            
            # Clean up Pandas NaN values so they display as N/A
            c_str = str(c_val) if pd.notna(c_val) and str(c_val).lower() != "nan" else "N/A"
            r_str = str(r_val) if pd.notna(r_val) and str(r_val).lower() != "nan" else "N/A"
            
            c_sec = time_to_seconds(c_str)
            r_sec = time_to_seconds(r_str)
            
            if r_sec and pb_sec and pb_sec <= r_sec:
                status_class = "qualified-regional"
                status_badge = "🏆 REGIONAL QUALIFIER"
            elif c_sec and pb_sec and pb_sec <= c_sec:
                status_class = "qualified-county"
                status_badge = "🌟 COUNTY QUALIFIER"

    def get_gap_html(pb, target):
        if not pb or not target: return ""
        diff = pb - target
        if diff <= 0: return f"<div class='gap-green'>✅ Qualified!</div>"
        return f"<div class='gap-red'>Drop {seconds_to_time(diff)}</div>"

    c_gap = get_gap_html(pb_sec, c_sec)
    r_gap = get_gap_html(pb_sec, r_sec)
    badge_html = f"<span class='badge {'achieved' if status_class else ''}'>{status_badge}</span>"

    # HTML is completely compressed to prevent Streamlit from interpreting it as a Markdown code block
    st.markdown(f"""<div class="pb-card {status_class}">
<div class="evt-title"><span>{evt}</span>{badge_html}</div>
<div class="grid">
<div class="box"><div class="box-label">Current PB</div><div class="box-val time-pb">{pb_str}</div></div>
<div class="box"><div class="box-label">County Target</div><div class="box-val">{c_str}</div>{c_gap}</div>
<div class="box"><div class="box-label">Regional Target</div><div class="box-val">{r_str}</div>{r_gap}</div>
</div></div>""", unsafe_allow_html=True)