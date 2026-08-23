import json, re
from bs4 import BeautifulSoup
from scrapling.fetchers import DynamicFetcher

keyword = 'biomedical'
url = 'https://globalink.mitacs.ca/#/student/application/projects'

page_setup_js = """
() => { window._captured_xhr = []; }
"""

page_action_js = """
(() => {
  const KEY = %s;
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
  function setKeywordAndSearch(){
    const input = findKeywordInput();
    if(input){
      try{ input.focus(); }catch(e){}
      input.value = KEY;
      input.dispatchEvent(new Event('input', {bubbles:true, composed:true}));
      input.dispatchEvent(new Event('change', {bubbles:true}));
      try{ input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true})); input.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', bubbles:true})); }catch(e){}
    }
    const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent||'').toLowerCase().includes('search and filter') || (b.textContent||'').toLowerCase().includes('search'));
    if(btn){ try{ btn.click(); }catch(e){} }
  }

  function collectEntriesFromDOM(){
    const entries = [];
    const candidates = Array.from(document.querySelectorAll('div, li, article'));
    const seen = new Set();
    for(const el of candidates){
      const txt = el.innerText || '';
      if((txt||'').toLowerCase().indexOf('project id')===-1) continue;
        if(!((txt||'').toLowerCase().indexOf('view detail')!==-1 || (txt||'').toLowerCase().indexOf('preferred start date')!==-1 || (txt||'').toLowerCase().indexOf('language')!==-1 || (txt||'').toLowerCase().indexOf('apply')!==-1)) continue;
      const key = txt.trim().slice(0,400);
      if(seen.has(key)) continue;
      seen.add(key);
      entries.push(el.outerHTML);
    }
    return entries;
  }

  setKeywordAndSearch();
  const wait = ms => new Promise(r => setTimeout(r, ms));
  return (async () => {
    await wait(1600);
    await wait(600);
    const pages = [];
    const p1 = collectEntriesFromDOM();
    pages.push(p1.join('\n<!--ENTRY_DELIM-->\n'));

    // Try to click numeric page '2' first
    let clicked = false;
    try{
      const num = Array.from(document.querySelectorAll('button, a, span')).find(n => (n.innerText||'').trim() === '2');
      if(num){ try{ num.click(); clicked = true; }catch(e){} }
    }catch(e){}
    if(!clicked){
      try{
        const nxt = document.querySelector('.p-paginator-next') || Array.from(document.querySelectorAll('button')).find(b => (b.getAttribute('aria-label')||'').toLowerCase().includes('next') || (b.innerText||'').trim() === '>');
        if(nxt){ try{ nxt.click(); clicked = true; }catch(e){} }
      }catch(e){}
    }
    if(clicked){
      await wait(1200);
      const p2 = collectEntriesFromDOM();
      pages.push(p2.join('\n<!--ENTRY_DELIM-->\n'));
    }

    const pre = document.createElement('pre'); pre.id='SCRAP_RESULT'; pre.style.display='none'; pre.textContent = pages.join('\n<!--PAGE_DELIM-->\n'); document.body.appendChild(pre);
  })();
})();
""" % (json.dumps(keyword))

print('Running interactive pagination verification for keyword:', keyword)
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=180000, wait=500, page_setup=lambda p: p.evaluate(page_setup_js), page_action=lambda p: p.evaluate(page_action_js))
body = getattr(resp, 'body', b'').decode('utf-8', errors='ignore')

m = re.search(r"<pre[^>]*id=['\"]SCRAP_RESULT['\"][^>]*>(.*?)</pre>", body, re.S)
if not m:
    print('No SCRAP_RESULT found')
    raise SystemExit(1)
pages_raw = m.group(1)
pages = pages_raw.split('\n<!--PAGE_DELIM-->\n') if pages_raw else []

print('Pages collected:', len(pages))

all_entries = []
for pi, p in enumerate(pages):
    entries = p.split('\n<!--ENTRY_DELIM-->\n') if p.strip() else []
    print(f' Page {pi+1} entries:', len(entries))
    for e in entries:
        all_entries.append((pi+1, e))

# parse first page entries (up to 11) and extract full description
from bs4 import BeautifulSoup

def extract_record_from_html(html):
    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text('\n', strip=True)
    m = re.search(r'Project ID\s*(\d+)', text)
    pid = m.group(1) if m else ''
    title = ''
    for tag in ['h1','h2','h3','h4','strong','b']:
        t = soup.find(tag)
        if t:
            ttxt = t.get_text('\n', strip=True)
            if ttxt and 'Project ID' not in ttxt:
                title = ttxt; break
    if not title:
        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        lines = [ln for ln in lines if not re.match(r'^(Faculty|Project Location|Language|Preferred start date|Project ID)', ln, re.I)]
        if lines: title = lines[0]
    # description: all <p> and long text blocks
    desc_parts = []
    for p in soup.find_all('p'):
        t = p.get_text('\n', strip=True)
        if t: desc_parts.append(t)
    if not desc_parts:
        # fallback: take lines after title until label
        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        if title in lines:
            idx = lines.index(title)
            for ln in lines[idx+1:idx+50]:
                if re.match(r'^(Faculty|Project Location|Language|Preferred start date|Project ID)', ln, re.I): break
                desc_parts.append(ln)
    description = '\n'.join(desc_parts).strip()
    return {'id': pid, 'title': title, 'description': description}

first_page_records = [extract_record_from_html(e_html) for (pg,e_html) in all_entries if pg==1][:11]
print('\nFirst page parsed records (up to 11):')
for r in first_page_records:
    print('-', r['id'], r['title'])

if first_page_records:
    print('\nFull multi-line description for first project:')
    print(first_page_records[0]['description'][:2000])
else:
    print('\nNo records parsed on first page')
