from scrapling.fetchers import DynamicFetcher
from bs4 import BeautifulSoup
import re

url = 'https://globalink.mitacs.ca/#/student/application/projects'

# Page action to perform search, then iterate paginator and collect page HTML into window._pages
PAGE_ACTION = ("""
() => {
  window._pages = [];
  function push_page(){
    try{
      window._pages.push(document.querySelector('body').innerHTML);
    }catch(e){ window._pages.push(document.documentElement.innerHTML); }
  }
  // set keyword input
  const input = Array.from(document.querySelectorAll('input')).find(i=> (i.placeholder||'').toLowerCase().includes('keyword'));
  if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); }
  // click search button
  const btn = Array.from(document.querySelectorAll('button')).find(b=> b.textContent && b.textContent.toLowerCase().includes('search'));
  if(btn) btn.click();

  function findNext(){
    // look for common paginator controls
    const nextCandidates = Array.from(document.querySelectorAll('button')).filter(b=> (b.textContent||'').toLowerCase().includes('next') || (b.className||'').toLowerCase().includes('next') || (b.getAttribute('aria-label')||'').toLowerCase().includes('next'));
    if(nextCandidates.length) return nextCandidates[0];
    // primeNG paginator
    const prim = document.querySelector('.p-paginator-next'); if(prim) return prim;
    return null;
  }

  // wait helper using polling
  function wait(ms){ return new Promise(r=> setTimeout(r, ms)); }

  return (async () => {
    await wait(1200);
    push_page();
    for(let i=0;i<200;i++){
      const nxt = findNext();
      if(!nxt) break;
      if(nxt.disabled || nxt.getAttribute('disabled')!==null) break;
      try{ nxt.click(); }catch(e){ break; }
      await wait(1200);
      push_page();
    }
    // expose collected pages in a pre element so it is available in the response body
    const pre = document.createElement('pre');
    pre.id = 'SCRAP_RESULT';
    pre.style.display='none';
    pre.textContent = window._pages.join('\n<!--PAGE_DELIM-->\n');
    document.body.appendChild(pre);
  })();
}
""")

print('Starting dynamic fetch and multi-page collection (may take a while)')
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=120000, wait=1000, page_action=lambda page: page.evaluate(PAGE_ACTION))
body = getattr(resp,'body',b'').decode('utf-8', errors='ignore')
# extract the SCRAP_RESULT content
m = re.search(r"<pre[^>]*id=['\"]SCRAP_RESULT['\"][^>]*>(.*?)</pre>", body, re.S)
if not m:
    print('No SCRAP_RESULT found; fallback to single-page parse')
    pages = [body]
else:
    data = m.group(1)
    pages = data.split('\n<!--PAGE_DELIM-->\n')
    print('Collected', len(pages), 'pages')

# For each page, extract project containers as before
records = []
for p in pages:
    soup = BeautifulSoup(p, 'lxml')
    for el in soup.find_all(string=re.compile(r'Faculty supervisor', re.I)):
        parent = el.parent
        for _ in range(6):
            if parent is None: break
            text = parent.get_text('\n', strip=True)
            if len(text) > 80 and text.lower().count('\n') >= 3:
                # parse
                rec = {}
                rec['raw'] = text
                m = re.search(r'Faculty supervisor:\s*(.+)', text, re.I)
                rec['supervisor'] = m.group(1).strip() if m else None
                m = re.search(r'Faculty University:\s*(.+)', text, re.I)
                rec['university'] = m.group(1).strip() if m else None
                m = re.search(r'Faculty Province:\s*(.+)', text, re.I)
                rec['province'] = m.group(1).strip() if m else None
                m = re.search(r'Project Location:\s*(.+)', text, re.I)
                rec['location'] = m.group(1).strip() if m else None
                if rec not in records:
                    records.append(rec)
                break
            parent = parent.parent

print('Total extracted records:', len(records))
for r in records[:20]:
    print('---')
    print(r)

# Optionally write to files
import json
with open('mitacs_projects_biomedical.json','w',encoding='utf-8') as fh:
    json.dump(records, fh, ensure_ascii=False, indent=2)
print('Wrote mitacs_projects_biomedical.json')
