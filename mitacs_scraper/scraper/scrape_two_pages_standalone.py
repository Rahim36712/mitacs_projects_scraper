import json, re, csv, time
from bs4 import BeautifulSoup
from scrapling.fetchers import DynamicFetcher

keyword = 'biomedical'
url = 'https://globalink.mitacs.ca/#/student/application/projects'
out_csv = r'D:/AI STUFF/PROJECTS/SCRAPER/mitacs_scraper/data/mitacs_projects_biomedical_2pages.csv'
max_pages = 2

capture_setup_js = """
() => {
  window._captured_xhr = [];
  try{ const origFetch = window.fetch; window.fetch = function(...args){ try{ window._captured_xhr.push({type:'fetch', url: args[0]}); }catch(e){} return origFetch.apply(this,args); }; }catch(e){}
  try{ const XHRproto = XMLHttpRequest.prototype; const origOpen = XHRproto.open; XHRproto.open = function(method, url){ try{ this._loggedUrl = url; }catch(e){} return origOpen.apply(this, arguments); }; const origSend = XHRproto.send; XHRproto.send = function(){ try{ window._captured_xhr.push({type:'xhr', url: this._loggedUrl}); }catch(e){} return origSend.apply(this, arguments); }; }catch(e){}
}
"""

page_action_js = """
() => {
  function findKeywordInput(){
    const labels = Array.from(document.querySelectorAll('.input-label, label, .header-container'));
    const kwLabel = labels.find(e => /Keyword search/i.test(e.textContent || ''));
    if(kwLabel){ let input = kwLabel.closest('div') ? kwLabel.closest('div').querySelector('input') : null; if(!input) input = kwLabel.parentElement ? kwLabel.parentElement.querySelector('input') : null; if(input) return input; }
    const inputs = Array.from(document.querySelectorAll('input'));
    for(const i of inputs){ if(i.offsetParent !== null) return i; }
    return null;
  }
  const KEY = %s;
  try{
    const input = findKeywordInput();
    if(input){ input.focus(); input.value = KEY; input.dispatchEvent(new Event('input',{bubbles:true, composed:true})); input.dispatchEvent(new Event('change',{bubbles:true})); try{ input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter', bubbles:true})); input.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter', bubbles:true})); }catch(e){} }
    const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent||'').toLowerCase().includes('search and filter') || (b.textContent||'').toLowerCase().includes('search'));
    if(btn){ try{ btn.click(); }catch(e){} }
  }catch(e){}

  const wait = (ms)=> new Promise(r=>setTimeout(r, ms));
  return (async ()=>{
    await wait(1400);
    const collected = [];
    function getContainerHtml(){
      const heading = Array.from(document.querySelectorAll('h1,h2,h3,h4,div,span')).find(e => /Project List/i.test((e.textContent||'')));
      let container = heading ? heading.closest('div') : null;
      if(!container) container = document.querySelector('.project-list') || document.querySelector('.p-grid') || document.body;
      return container ? container.innerHTML : document.documentElement.innerHTML;
    }
    collected.push(getContainerHtml());
    for(let i=1;i<%d;i++){
      // try to click next
      let nxt = document.querySelector('.p-paginator-next') || Array.from(document.querySelectorAll('button')).find(b=> (b.getAttribute('aria-label')||'').toLowerCase().includes('next') || (b.textContent||'').trim()=='>' );
      if(!nxt) break;
      if(nxt.disabled || (nxt.className||'').toLowerCase().includes('p-disabled')) break;
      try{ nxt.click(); }catch(e){ break; }
      await wait(1000);
      collected.push(getContainerHtml());
    }
    // attach results
    try{ const pre = document.createElement('pre'); pre.id='SCRAP_RESULT'; pre.style.display='none'; pre.textContent = collected.join('\n<!--PAGE_DELIM-->\n'); document.body.appendChild(pre); }catch(e){}
    try{ const pre2 = document.createElement('pre'); pre2.id='XHR_CAPTURE'; pre2.style.display='none'; pre2.textContent = JSON.stringify(window._captured_xhr || []); document.body.appendChild(pre2); }catch(e){}
  })();
}
""" % (json.dumps(keyword), max_pages)

print('Starting scrape (2 pages) for keyword:', keyword)
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=180000, wait=500, page_setup=lambda page: page.evaluate(capture_setup_js), page_action=lambda page: page.evaluate(page_action_js))
body = getattr(resp, 'body', b'').decode('utf-8', errors='ignore')

m = re.search(r"<pre[^>]*id=['\"]SCRAP_RESULT['\"][^>]*>(.*?)</pre>", body, re.S)
pages = []
if m:
    pages = m.group(1).split('\n<!--PAGE_DELIM-->\n')
else:
    pages = [body]

# parser similar to parse_projects_from_page
from bs4 import BeautifulSoup

def normalize_text(s):
    if s is None: return ''
    return ' '.join(s.split()).strip()

def parse_projects_from_page(html):
    soup = BeautifulSoup(html, 'lxml')
    records = []
    markers = soup.find_all(string=re.compile(r'Project ID\s*(\d+)', re.I))
    for marker in markers:
        m_id = re.search(r'Project ID\s*(\d+)', marker, re.I)
        pid = m_id.group(1).strip() if m_id else None
        parent = marker.parent
        container = None
        for _ in range(8):
            if parent is None: break
            text = parent.get_text('\n', strip=True)
            if pid and pid in text and len(text) > 60:
                container = parent; break
            parent = parent.parent
        if container is None: continue
        rec = {'id': pid, 'title': '', 'description': '', 'start_date': '', 'language': ''}
        title = None
        for tag in ['h1','h2','h3','h4','strong','b']:
            ttag = container.find(tag)
            if ttag:
                ttxt = ttag.get_text('\n', strip=True)
                if ttxt and 'Project ID' not in ttxt and len(ttxt) > 3:
                    title = ttxt; break
        if not title:
            lines = [ln.strip() for ln in container.get_text('\n').split('\n') if ln.strip()]
            lines = [ln for ln in lines if not re.match(r'^(Faculty|Project Location|Language|Preferred start date|Project ID)', ln, re.I)]
            if lines: title = lines[0]
        rec['title'] = normalize_text(title or '')
        desc = ''
        for p in container.find_all('p'):
            txt = p.get_text('\n', strip=True)
            if len(txt) >= 40:
                desc = txt; break
        if not desc:
            all_lines = [ln.strip() for ln in container.get_text('\n').split('\n') if ln.strip()]
            if title and title in all_lines:
                idx = all_lines.index(title)
                candidate_lines = []
                for ln in all_lines[idx+1:idx+6]:
                    if re.match(r'^(Faculty|Project Location|Language|Preferred start date|Project ID)', ln, re.I): break
                    candidate_lines.append(ln)
                desc = ' '.join(candidate_lines)
            else:
                blocks = re.split(r'\n{2,}', container.get_text('\n'))
                blocks = [b.strip() for b in blocks if len(b.strip())>40]
                if blocks: desc = blocks[0]
        rec['description'] = normalize_text(desc or '')
        ctext = container.get_text('\n', strip=True)
        m = re.search(r'Preferred start date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})', ctext, re.I)
        if m: rec['start_date'] = m.group(1)
        else:
            m = re.search(r'Preferred start date:\s*([0-9]{4}-[0-9]{2})', ctext, re.I)
            if m: rec['start_date'] = m.group(1)
        m = re.search(r'Language:\s*([A-Za-z]+)', ctext, re.I)
        if m: rec['language'] = m.group(1).strip()
        records.append(rec)
    return records

all_records = []
for p in pages:
    recs = parse_projects_from_page(p)
    all_records.extend(recs)

# dedupe
seen = set(); rows = []
for r in all_records:
    pid = r.get('id')
    if pid in seen: continue
    seen.add(pid)
    rows.append({'id': r.get('id') or '', 'title': r.get('title') or '', 'description': r.get('description') or '', 'start_date': r.get('start_date') or '', 'language': r.get('language') or ''})

# write CSV
fieldnames = ['id','title','description','start_date','language']
with open(out_csv, 'w', encoding='utf-8', newline='') as fh:
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

print('Wrote', len(rows), 'records to', out_csv)
