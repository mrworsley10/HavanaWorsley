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
        
        # Scan all tables on the page to find the specific Summary Table
        for table in soup.find_all('table'):
            sc_idx = -1
            lc_idx = -1
            
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if not cells: continue
                
                # 1. Identify the correct columns from the header row
                if sc_idx == -1:
                    for i, c in enumerate(cells):
                        c_lower = c.lower()
                        if "short course pb" in c_lower: sc_idx = i
                        elif "long course pb" in c_lower: lc_idx = i
                    continue # Move to the next row once headers are mapped
                
                # If we are in a table that doesn't have these columns, break out and check the next table
                if sc_idx == -1 or lc_idx == -1: break
                
                # 2. Extract the Data
                event_name = cells[0]
                if not re.search(r'\d+m\s+[A-Za-z]+', event_name, re.IGNORECASE):
                    continue
                    
                clean_evt = extract_standard_event(event_name)
                if not clean_evt: continue
                
                # Make sure the row has enough columns
                if len(cells) > max(sc_idx, lc_idx):
                    sc_time = cells[sc_idx]
                    lc_time = cells[lc_idx]
                    
                    # Add Short Course (25m) PB if it isn't a dot
                    if sc_time and sc_time != '.':
                        all_swims.append({"Event": clean_evt, "Course": "25m", "Time": sc_time})
                        
                    # Add Long Course (50m) PB if it isn't a dot
                    if lc_time and lc_time != '.':
                        all_swims.append({"Event": clean_evt, "Course": "50m", "Time": lc_time})
            
            # If we successfully parsed the summary table, stop looking at other tables
            if sc_idx != -1: break
            
        return pd.DataFrame(all_swims)
        
    except Exception as e:
        st.error(f"Failed to fetch PB times: {e}")
        return pd.DataFrame()