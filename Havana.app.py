# --- WEB SCRAPER FOR SWIM ENGLAND PBS ---
@st.cache_data(ttl=3600) # Caches the data for 1 hour to keep it fast
def scrape_swim_england_pbs(url):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Upgraded headers to bypass basic bot-protection blocks
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-GB,en;q=0.9,en-US;q=0.8'
    }
    
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        records = []
        for tr in soup.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if not cells or "Event" in cells: continue
            
            event_name, course, time_val = "", "", ""
            
            for c in cells:
                c_upper = c.upper()
                if re.search(r'\d+m\s+[A-Za-z]+', c, re.IGNORECASE): 
                    event_name = c
                # Fix: Catch "25", "50", "SC", "LC" as they appear on official DBs
                elif c_upper in ["25", "50", "25M", "50M", "SC", "LC"]: 
                    if "25" in c_upper or "SC" in c_upper: course = "25m"
                    else: course = "50m"
                elif re.match(r'^[\d\:\.]+$', c) and ('.' in c or ':' in c): 
                    time_val = c
                    
            if event_name and time_val and course:
                clean_evt = extract_standard_event(event_name)
                if clean_evt:
                    # Prevent duplicates (Swim England sorts by fastest PB first, so we keep the first one we see)
                    if not any(r['Event'] == clean_evt and r['Course'] == course for r in records):
                        records.append({"Event": clean_evt, "Course": course, "Time": time_val})
                        
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Failed to fetch PB times: {e}")
        return pd.DataFrame()