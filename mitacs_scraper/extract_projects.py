from scrapling.fetchers import DynamicFetcher
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

url = 'https://globalink.mitacs.ca/#/student/application/projects'
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=2000, page_action=lambda page: page.evaluate("() => { const input = Array.from(document.querySelectorAll('input')).find(i => (i.placeholder||'').toLowerCase().includes('keyword')); if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); } var btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.toLowerCase().includes('search')); if(btn) btn.click(); }"))
body = getattr(resp, 'body', b'')
soup = BeautifulSoup(body, 'lxml')

# Heuristic: find elements that contain "Faculty supervisor" and treat their nearest ancestor with multiple fields as a project container.
project_containers = []
for el in soup.find_all(string=re.compile(r'Faculty supervisor', re.I)):
    parent = el.parent
    # climb up until we find a container with several children
    for _ in range(6):
        if parent is None:
            break
        text = parent.get_text('\n', strip=True)
        if len(text) > 80 and text.lower().count('\n') >= 3:
            project_containers.append(parent)
            break
        parent = parent.parent

# Deduplicate by text
seen = set()
records = []
for c in project_containers:
    t = c.get_text('\n', strip=True)
    if t in seen:
        continue
    seen.add(t)
    # extract fields by label
    rec = {'title': None, 'supervisor': None, 'university': None, 'province': None, 'location': None, 'preferred_start': None, 'raw': t}
    # Supervisor
    m = re.search(r'Faculty supervisor:\s*(.+)', t, re.I)
    if m:
        rec['supervisor'] = m.group(1).strip()
    m = re.search(r'Faculty University:\s*(.+)', t, re.I)
    if m:
        rec['university'] = m.group(1).strip()
    m = re.search(r'Faculty Province:\s*(.+)', t, re.I)
    if m:
        rec['province'] = m.group(1).strip()
    m = re.search(r'Project Location:\s*(.+)', t, re.I)
    if m:
        rec['location'] = m.group(1).strip()
    m = re.search(r'Preferred start date:\s*(.+)', t, re.I)
    if m:
        rec['preferred_start'] = m.group(1).strip()
    records.append(rec)

print('Extracted', len(records), 'records (sample 10):')
for r in records[:10]:
    print('---')
    print('Supervisor:', r['supervisor'])
    print('University:', r['university'])
    print('Province:', r['province'])
    print('Location:', r['location'])
    print('Preferred start:', r['preferred_start'])
    print('Raw snippet:', r['raw'][:200])
