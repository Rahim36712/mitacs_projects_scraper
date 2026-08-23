from scrapling.fetchers import DynamicFetcher
from bs4 import BeautifulSoup
import re, json

url = 'https://globalink.mitacs.ca/#/student/application/projects'
PAGE_ACTION = '''
() => {
  window._collected = [];
  function push(){ try{ window._collected.push(document.querySelector('body').innerHTML); }catch(e){ window._collected.push(document.documentElement.innerHTML); } }
  const input = Array.from(document.querySelectorAll('input')).find(i=> (i.placeholder||'').toLowerCase().includes('keyword'));
  if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); }
  const btn = Array.from(document.querySelectorAll('button')).find(b=> b.textContent && b.textContent.toLowerCase().includes('search'));
  if(btn) btn.click();
  const wait = (ms)=> new Promise(r=>setTimeout(r, ms));
  return (async ()=>{
    await wait(1200);
    push();
    for(let i=0;i<100;i++){
      let nxt = document.querySelector('.p-paginator-next') || Array.from(document.querySelectorAll('button')).find(b=> (b.getAttribute('aria-label')||'').toLowerCase().includes('next'));
      if(!nxt) break;
      if(nxt.disabled || nxt.className.indexOf('p-disabled')!==-1) break;
      try{ nxt.click(); }catch(e){ break; }
      await wait(1200);
      push();
    }
    const pre = document.createElement('pre'); pre.id='SCRAP_RESULT'; pre.style.display='none'; pre.textContent = window._collected.join('\n<!--PAGE_DELIM-->\n'); document.body.appendChild(pre);
  })();
}
'''

print('Running multi-page collection (may take a few minutes)')
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=180000, wait=500, page_action=lambda page: page.evaluate(PAGE_ACTION))
body = getattr(resp,'body',b'').decode('utf-8', errors='ignore')
match = re.search(r"<pre[^>]*id=['\"]SCRAP_RESULT['\"][^>]*>(.*?)</pre>", body, re.S)
if not match:
    print('No SCRAP_RESULT — no pages collected (fallback to single page)')
    pages = [body]
else:
    data = match.group(1)
    pages = data.split('\n<!--PAGE_DELIM-->\n')
    print('Collected pages:', len(pages))

# Extract records
records = []
for p in pages:
    soup = BeautifulSoup(p, 'lxml')
    for el in soup.find_all(string=re.compile(r'Faculty supervisor', re.I)):
        parent = el.parent
        for _ in range(6):
            if parent is None: break
            text = parent.get_text('\n', strip=True)
            if len(text) > 80 and text.lower().count('\n') >= 3:
                rec = {'raw': text}
                import re
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

print('Total records extracted:', len(records))
with open('mitacs_projects_biomedical_full.json','w',encoding='utf-8') as fh:
    json.dump(records, fh, ensure_ascii=False, indent=2)
print('Wrote mitacs_projects_biomedical_full.json')
