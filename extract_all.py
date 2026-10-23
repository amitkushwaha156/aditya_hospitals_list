import fitz
import re
import json
import os
import time

start_time = time.time()

pdf_path = 'Aditya_Birla_Health_Smart_2026.pdf'
print(f"Opening {pdf_path}...")
doc = fitz.open(pdf_path)
total_pages = len(doc)
print(f"Total pages to process: {total_pages}")

INDIAN_STATES = [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Chattisgarh',
    'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala',
    'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland',
    'Odisha', 'Orissa', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana',
    'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'Uttaranchal', 'West Bengal',
    'Delhi', 'Jammu And Kashmir', 'Jammu & Kashmir', 'Ladakh', 'Puducherry', 'Pondicherry',
    'Chandigarh', 'Dadra And Nagar Haveli', 'Daman And Diu', 'Andaman And Nicobar'
]

state_parts = [r'\s+'.join(re.escape(w) for w in s.split()) for s in INDIAN_STATES]
state_parts.sort(key=len, reverse=True)
state_regex_str = '|'.join(state_parts)

end_entry_pattern = re.compile(rf'({state_regex_str})\s*,\s*(\d{{6}})', re.IGNORECASE)

def detect_specialty(name, address):
    combined = f"{name} {address}".lower()
    tags = []
    
    # Eye
    if re.search(r'\b(eye|netra|netralaya|drishti|vision|ophthalm\w*|retina|sight|cornea|glaucoma|cataract)\b', combined):
        tags.append('Eye Care')
        
    # Heart
    if re.search(r'\b(heart|cardio\w*|cardiac|coronary|vascular)\b', combined):
        tags.append('Heart / Cardiology')
        
    # Cancer
    if re.search(r'\b(cancer|oncol\w*|tumor|tumour|chemo\w*|radiotherapy|carcinoma)\b', combined):
        tags.append('Cancer / Oncology')
        
    # Kidney / Urology
    if re.search(r'\b(kidney|uro\w*|urology|renal|dialysis|nephro\w*|lithotripsy|stone clinic)\b', combined):
        tags.append('Kidney / Urology')
        
    # Ortho / Bone / Joint
    if re.search(r'\b(ortho\w*|bone|joint|spine|fracture|trauma|accident)\b', combined):
        tags.append('Ortho / Bone / Joint')
        
    # Child / Pediatric / Maternity
    if re.search(r'\b(child\w*|pediatric\w*|paediatric\w*|maternity|mother\w*|women\w*|woman|ivf|fertility|gynec\w*|gynaec\w*|obstetric\w*|neonatal|newborn|baby|shishu)\b', combined):
        tags.append('Child / Pediatric & Maternity')
        
    # Dental
    if re.search(r'\b(dental|tooth|teeth|dento\w*|oral)\b', combined):
        tags.append('Dental Care')
        
    # ENT
    if re.search(r'\b(ent|ear|throat)\b', combined) and not re.search(r'\b(centre|center|patient|department)\b', combined):
        tags.append('ENT Care')
        
    # Neuro
    if re.search(r'\b(neuro\w*|brain|stroke|psychiatr\w*)\b', combined):
        tags.append('Neurology / Brain')

    # Ayurveda
    if re.search(r'\b(ayur\w*|naturopath\w*|nature cure|homeo\w*|siddha|unani)\b', combined):
        tags.append('Ayurveda & Alternative Care')

    # Multispeciality
    is_multi = bool(re.search(r'\b(multi\w*|super\s*spec\w*|superspeciality)\b', combined))
    
    if tags:
        if is_multi and not any('Multispeciality' in t for t in tags):
            tags.append('Multispeciality')
        return ' & '.join(tags)
    
    if is_multi:
        return 'Multispeciality'
    
    if re.search(r'\b(hospital|nursing home|clinic|medicare|health\s*care|medical|institute)\b', combined):
        return 'General Hospital'
        
    return 'Multispeciality / General'

def clean_address(addr):
    # Remove repeated segments (e.g. phrase repeated 2-3 times)
    for _ in range(2):
        addr = re.sub(r'([A-Za-z0-9\s\/\.\-\#]{12,}?)(?:,\s*\1)+', r'\1', addr)
    addr = re.sub(r'\s+', ' ', addr).strip()
    return addr

def parse_column_text(text, pno):
    entries = []
    if pno == 0:
        lines = text.split('\n')
        filtered = []
        for l in lines:
            if any(h in l for h in ['List of hospitals', 'Last updated', 'Supplier Name', 'Aditya Birla', 'Disclaimer:']):
                continue
            filtered.append(l)
        text = '\n'.join(filtered)
    
    last_end = 0
    for m in end_entry_pattern.finditer(text):
        raw_entry = text[last_end:m.end()].strip()
        last_end = m.end()
        raw_entry = re.sub(r'^[\s\xa0\.\,\-\"\']+', '', raw_entry).strip()
        if not raw_entry:
            continue
        
        state_matched = re.sub(r'\s+', ' ', m.group(1)).title()
        # Normalize state names
        if state_matched == 'Chattisgarh':
            state_matched = 'Chhattisgarh'
        elif state_matched == 'Orissa':
            state_matched = 'Odisha'
        elif state_matched == 'Uttaranchal':
            state_matched = 'Uttarakhand'
        elif state_matched == 'Pondicherry':
            state_matched = 'Puducherry'
        elif state_matched == 'Jammu And Kashmir':
            state_matched = 'Jammu & Kashmir'
            
        pincode_matched = m.group(2)
        
        city_m = re.search(r'\(City\s*-\s*([^)]+)\)', raw_entry, re.IGNORECASE)
        city = ''
        if city_m:
            city = city_m.group(1).strip()
            city = re.sub(r'[\r\n]+', ' ', city).strip().title()
        
        lines = [l.strip() for l in raw_entry.split('\n') if l.strip() and l.strip() != '\xa0']
        if not lines:
            continue
            
        name = lines[0]
        addr_start_idx = 1
        if len(lines) > 2:
            if (name.startswith('"') and not name.endswith('"')) or re.search(r'\b(Of|And|&|A Unit Of|The|Institute Of|Hospital And|Care And|Hospital &)\s*$', name, re.IGNORECASE):
                name = name + ' ' + lines[1]
                addr_start_idx = 2
                
        name = name.strip(' "\'.,-')
        addr = ' '.join(lines[addr_start_idx:])
        addr = clean_address(addr)
        
        if not city:
            before_state_m = re.search(r',\s*([^,]+)\s*,\s*' + re.escape(m.group(1)), raw_entry, re.IGNORECASE)
            if before_state_m:
                city = before_state_m.group(1).strip().title()
        if not city:
            city = 'Other'
            
        specialty = detect_specialty(name, addr)
        
        entries.append({
            'name': name,
            'city': city,
            'state': state_matched,
            'pincode': pincode_matched,
            'address': addr,
            'specialty': specialty
        })
    return entries

cols = [fitz.Rect(0, 0, 292, 842), fitz.Rect(292, 0, 595, 842)]
all_hospitals = []
seen_keys = set()
duplicates_count = 0

print("Processing all 457 pages...")
for p in range(total_pages):
    page = doc[p]
    for c_idx, r in enumerate(cols):
        t = page.get_text('text', clip=r)
        parsed = parse_column_text(t, p)
        for h in parsed:
            # Deduplication key: lowercase name + city + pincode
            key = (h['name'].lower().strip(), h['city'].lower().strip(), h['pincode'])
            if key in seen_keys:
                duplicates_count += 1
                continue
            seen_keys.add(key)
            all_hospitals.append(h)
            
    if (p + 1) % 50 == 0 or (p + 1) == total_pages:
        print(f"  Processed {p+1}/{total_pages} pages -> {len(all_hospitals)} unique hospitals found so far")

elapsed = time.time() - start_time
print(f"\nDone in {elapsed:.2f} seconds!")
print(f"Total Unique Hospitals Extracted: {len(all_hospitals)}")
print(f"Duplicates Filtered Out: {duplicates_count}")

# Save to JSON
json_path = 'hospitals_data.json'
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(all_hospitals, f, ensure_ascii=False, indent=2)
print(f"Saved JSON to {json_path} ({os.path.getsize(json_path) / (1024*1024):.2f} MB)")

# Also save as minified JS file for direct web embedding without CORS issues
js_path = 'hospitals_data.js'
with open(js_path, 'w', encoding='utf-8') as f:
    f.write('const hospitalsData = ')
    json.dump(all_hospitals, f, ensure_ascii=False)
    f.write(';\n')
print(f"Saved JS to {js_path} ({os.path.getsize(js_path) / (1024*1024):.2f} MB)")

# Print statistics
cities = set(h['city'] for h in all_hospitals if h['city'])
states = set(h['state'] for h in all_hospitals if h['state'])
specialties = set(h['specialty'] for h in all_hospitals)

print(f"\nTotal Unique Cities Covered: {len(cities)}")
print(f"Total States Covered: {len(states)}")
print(f"Top 10 Cities by Hospital Count:")
from collections import Counter
city_counts = Counter(h['city'] for h in all_hospitals).most_common(10)
for c, cnt in city_counts:
    print(f"  - {c}: {cnt}")
