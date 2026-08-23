import json, re, time
from bs4 import BeautifulSoup
from scrapling.fetchers import DynamicFetcher

keyword = 'biomedical'
url = 'https://globalink.mitacs.ca/#/student/application/projects'

# page setup: nothing special
capture_setup_js = """
() => { window._captured_xhr = []; }
"""

# page action: robust typing + click
page_action_js = """
() => {
  function findKeywordInput(){
    const labels = Array.from(document.querySelectorAll('.input-label, label, .header-container'));
    const kwLabel = labels.find(e => /Keyword search/i.test(e.textContent || ''));
    if(kwLabel){
      let input = kwLabel.closest('div') ? kwLabel.closest('div').querySelector('input') : null;
      if(!input) input = kwLabel.parentElement ? kwLabel.parentElement.querySelector('input') : null;
      if(input) return input;
    }
    const inputs = Array.from(document.querySelectorAll('input'));
    for(const i of inputs){ if(i.offsetParent !== null) return i; }
    return null;
  }
  const KEY = %s;
  const input = findKeywordInput();
  if(input){
    input.focus();
    // set value and trigger events
    input.value = KEY;
    input.dispatchEvent(new Event('input', {bubbles:true, composed:true}));
    input.dispatchEvent(new Event('change', {bubbles:true}));
    try{ input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true})); input.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', bubbles:true})); }catch(e){}
  }
  // click Search button
  const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent||'').toLowerCase().includes('search and filter') || (b.textContent||'').toLowerCase().includes('search'));
  if(btn){ try{ btn.click(); }catch(e){} }

  // wait a bit
  const wait = (ms)=> new Promise(r=>setTimeout(r, ms));
  return (async ()=>{
    await wait(1600);
    await wait(800);
    // find project list container
    const heading = Array.from(document.querySelectorAll('h1,h2,h3,h4,div,span')).find(e => /Project List/i.test((e.textContent||'')));
    let container = heading ? heading.closest('div') : null;
    if(!container) container = document.querySelector('.project-list') || document.querySelector('.p-grid') || document.body;
    const html = container ? container.innerHTML : document.documentElement.innerHTML;
    const pre = document.createElement('pre'); pre.id='SCRAP_RESULT'; pre.style.display='none'; pre.textContent = html; document.body.appendChild(pre);
  })();
}
""" % (json.dumps(keyword))

print('Running verification with full-list extraction for keyword:', keyword)
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=180000, wait=500, page_setup=lambda page: page.evaluate(capture_setup_js), page_action=lambda page: page.evaluate(page_action_js))
body = getattr(resp, 'body', b'').decode('utf-8', errors='ignore')

m = re.search(r"<pre[^>]*id=['\"]SCRAP_RESULT['\"][^>]*>(.*?)</pre>", body, re.S)
html = m.group(1) if m else body

# parse container: find project containers by locating 'View Detail' buttons and taking their closest ancestor
soup = BeautifulSoup(html, 'lxml')
# find elements that look like view-detail buttons
buttons = soup.find_all(string=re.compile(r'View Detail', re.I))
containers = []
for b in buttons:
    try:
        elem = b.parent
        # climb to a containing div
        for _ in range(8):
            if elem is None: break
            if elem.name == 'div' and len(elem.get_text(strip=True)) > 20:
                containers.append(elem)
                break
            elem = elem.parent
    except Exception:
        pass

# fallback: find markers 'Project ID' and dedupe containers
if not containers:
    markers = soup.find_all(string=re.compile(r'Project ID\s*(\d+)', re.I))
    for marker in markers:
        parent = marker.parent
        for _ in range(8):
            if parent is None: break
            if parent.name == 'div' and len(parent.get_text(strip=True)) > 20:
                containers.append(parent); break
            parent = parent.parent

# dedupe containers by their text
seen = set(); unique_containers = []
for c in containers:
    txt = c.get_text('\n', strip=True)[:200]
    if txt in seen: continue
    seen.add(txt); unique_containers.append(c)

print('Detected project containers on page:', len(unique_containers))

results = []
for idx, c in enumerate(unique_containers[:15]):
    ctext = c.get_text('\n', strip=True)
    m_id = re.search(r'Project ID\s*(\d+)', ctext)
    pid = m_id.group(1) if m_id else ''
    # title: first h* or bold or first non-label line
    title = ''
    for tag in ['h1','h2','h3','h4','strong','b']:
        t = c.find(tag)
        if t:
            ttxt = t.get_text('\n', strip=True)
            if ttxt and 'Project ID' not in ttxt:
                title = ttxt; break
    if not title:
        lines = [ln.strip() for ln in c.get_text('\n').split('\n') if ln.strip()]
        lines = [ln for ln in lines if not re.match(r'^(Faculty|Project Location|Language|Preferred start date|Project ID)', ln, re.I)]
        if lines: title = lines[0]
    # description: join all <p> inside container, if none, take the block of lines between title and next label
    desc_parts = []
    for p in c.find_all('p'):
        txt = p.get_text('\n', strip=True)
        if txt:
            desc_parts.append(txt)
    if not desc_parts:
        # take lines after title until label
        all_lines = [ln.strip() for ln in c.get_text('\n').split('\n') if ln.strip()]
        if title in all_lines:
            idx_line = all_lines.index(title)
            for ln in all_lines[idx_line+1:idx_line+30]:
                if re.match(r'^(Faculty|Project Location|Language|Preferred start date|Project ID)', ln, re.I): break
                desc_parts.append(ln)
    description = '\n'.join(desc_parts).strip()
    results.append({'id': pid, 'title': title, 'description': description})

# print top 11 and full description of first project
print('\nTop projects (up to 11):')
for r in results[:11]:
    print('-', r['id'], r['title'])

if results:
    print('\nFull description for first project:')
    print(results[0]['description'])
else:
    print('\nNo project results parsed.')

# also print on-page total
m_total = re.search(r'Total number of projects\s*:\s*(\d+)', html, re.I)
if m_total:
    print('\nOn-page total:', int(m_total.group(1)))

# print captured XHRs if any
m2 = re.search(r"<pre[^>]*id=['\"]XHR_CAPTURE['\"][^>]*>(.*?)</pre>", body, re.S)
if m2:
    try:
        cap = json.loads(m2.group(1))
        print('\nCaptured XHRs:', json.dumps(cap, indent=2))
    except Exception:
        pass
