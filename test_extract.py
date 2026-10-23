import fitz
import re
import json

doc = fitz.open('Aditya_Birla_Health_Smart_2026.pdf')

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
    combined = (name + ' ' + address).lower()
    
    tags = []
    
    # Eye
    if any(k in combined for k in ['eye', 'netra', 'drishti', 'vision', 'ophthalm', 'retina', 'sight', 'cornea']):
        tags.append('Eye Care')
        
    # Heart
    if any(k in combined for k in ['heart', 'cardio', 'cardiac', 'vascular', 'coronary']):
        tags.append('Heart / Cardiology')
        
    # Cancer
    if any(k in combined for k in ['cancer', 'oncol', 'tumor', 'tumour', 'chemo', 'radiotherapy']):
        tags.append('Cancer / Oncology')
        
    # Kidney / Urology
    if any(k in combined for k in ['kidney', 'uro', 'renal', 'dialysis', 'nephro', 'stone clinic']):
        tags.append('Kidney / Urology')
        
    # Ortho / Bone / Joint
    if any(k in combined for k in ['ortho', 'bone', 'joint', 'spine', 'fracture', 'trauma', 'accident']):
        tags.append('Ortho / Bone / Joint')
        
    # Child / Pediatric / Maternity
    if any(k in combined for k in ['child', 'pediatric', 'paediatric', 'maternity', 'mother', 'women', 'woman', 'ivf', 'fertility', 'gynec', 'gynaec', 'obstetric', 'neonatal', 'newborn', 'baby', 'shishu']):
        tags.append('Child / Pediatric & Maternity')
        
    # Dental
    if any(k in combined for k in ['dental', 'tooth', 'teeth', 'dento', 'oral']):
        tags.append('Dental Care')
        
    # ENT
    if any(k in combined for k in [' ent ', 'ent hospital', 'ear', 'throat', 'ent care']):
        tags.append('ENT Care')
        
    # Neuro
    if any(k in combined for k in ['neuro', 'brain', 'stroke', 'mind', 'psychiatr']):
        tags.append('Neurology / Neuro')

    # Ayurveda
    if any(k in combined for k in ['ayur', 'naturopathy', 'nature cure', 'homeo', 'siddha', 'unani']):
        tags.append('Ayurveda & Alternative Care')

    # Multispeciality / General
    is_multi = any(k in combined for k in ['multi', 'super spec', 'superspeciality', 'general', 'critical care', 'medicare', 'research centre', 'medical centre', 'lifeline', 'hospital', 'nursing home'])
    
    if tags:
        if is_multi and not any('Multispeciality' in t for t in tags):
            if 'Multispeciality' in combined or 'super' in combined:
                tags.append('Multispeciality')
        return ' & '.join(tags)
    
    if is_multi:
        if 'multi' in combined or 'super' in combined:
            return 'Multispeciality'
        return 'General Hospital'
        
    return 'Multispeciality / General'

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
            if (name.startswith('"') and not name.endswith('"')) or re.search(r'\b(Of|And|&|A Unit Of|The|Institute Of|Hospital And|Care And)\s*$', name, re.IGNORECASE):
                name = name + ' ' + lines[1]
                addr_start_idx = 2
                
        name = name.strip(' "\'.,-')
        addr = ' '.join(lines[addr_start_idx:])
        addr = re.sub(r'\s+', ' ', addr).strip()
        
        # If city not found from (City - ...), try to extract before state
        if not city:
            before_state_m = re.search(r',\s*([^,]+)\s*,\s*' + re.escape(m.group(1)), raw_entry, re.IGNORECASE)
            if before_state_m:
                city = before_state_m.group(1).strip().title()
        
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

# Test first 10 pages
cols = [fitz.Rect(0, 0, 292, 842), fitz.Rect(292, 0, 595, 842)]
all_entries = []
for p in range(10):
    page = doc[p]
    for c_idx, r in enumerate(cols):
        t = page.get_text('text', clip=r)
        parsed = parse_column_text(t, p)
        all_entries.extend(parsed)

print(f'Parsed {len(all_entries)} entries from 10 pages.')
print('\n--- FIRST 5 ENTRIES ---')
for e in all_entries[:5]:
    print(json.dumps(e, indent=2))

print('\n--- SAMPLES WITH EYE ---')
eye_samples = [e for e in all_entries if 'Eye' in e['specialty']][:2]
for e in eye_samples:
    print(json.dumps(e, indent=2))

print('\n--- SAMPLES WITH HEART ---')
heart_samples = [e for e in all_entries if 'Heart' in e['specialty']][:2]
for e in heart_samples:
    print(json.dumps(e, indent=2))
