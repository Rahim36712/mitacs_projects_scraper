import json, re, time
from bs4 import BeautifulSoup
from scrapling.fetchers import DynamicFetcher

keyword = 'biomedical'
url = 'https://globalink.mitacs.ca/#/student/application/projects'

# JS to capture XHR/fetch calls
capture_setup_js = """
() => {
  window._captured_xhr = [];
  try{
    const origFetch = window.fetch;
    window.fetch = function(...args){ try{ window._captured_xhr.push({type:'fetch', url: args[0]}); }catch(e){} return origFetch.apply(this,args); };
  }catch(e){}
  try{
    const XHRproto = XMLHttpRequest.prototype;
    const origOpen = XHRproto.open;
    XHRproto.open = function(method, url){ try{ this._loggedUrl = url; }catch(e){} return origOpen.apply(this, arguments); };
    const origSend = XHRproto.send;
    XHRproto.send = function(){ try{ window._captured_xhr.push({type:'xhr', url: this._loggedUrl}); }catch(e){} return origSend.apply(this, arguments); };
  }catch(e){}
}
"""

# JS action: set keyword and click search, then build SCRAP_RESULT and XHR_CAPTURE pres
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
    input.value = KEY;
    input.dispatchEvent(new Event('input', {bubbles:true, composed:true}));
    input.dispatchEvent(new Event('change', {bubbles:true}));
    try{ input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true})); input.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', bubbles:true})); }catch(e){}
  }
  const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent||'').toLowerCase().includes('search and filter') || (b.textContent||'').toLowerCase().includes('search'));
  if(btn){ try{ btn.click(); }catch(e){} }

  const wait = (ms)=> new Promise(r=>setTimeout(r, ms));
  return (async ()=>{
    await wait(1600);
    // try to let network settle
    try{ if(window && window.fetch){ await wait(800); } }catch(e){}

    // find project-list container
    const heading = Array.from(document.querySelectorAll('h1,h2,h3,h4,div,span')).find(e => /Project List/i.test((e.textContent||'')));
    let container = null;
    if(heading) container = heading.closest('div');
    if(!container) container = document.querySelector('.project-list') || document.querySelector('.p-grid') || document.body;
    const html = container ? container.innerHTML : document.documentElement.innerHTML;
    const pre = document.createElement('pre'); pre.id='SCRAP_RESULT'; pre.style.display='none'; pre.textContent = html; document.body.appendChild(pre);
    try{ const pre2 = document.createElement('pre'); pre2.id='XHR_CAPTURE'; pre2.style.display='none'; pre2.textContent = JSON.stringify(window._captured_xhr || []); document.body.appendChild(pre2); }catch(e){}
  })();
}
""" % (json.dumps(keyword))

print('Running dynamic fetch verification for keyword:', keyword)
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=180000, wait=500, page_setup=lambda page: page.evaluate(capture_setup_js), page_action=lambda page: page.evaluate(page_action_js))
body = getattr(resp, 'body', b'').decode('utf-8', errors='ignore')

# extract the SCRAP_RESULT content if present
m = re.search(r"<pre[^>]*id=['\"]SCRAP_RESULT['\"][^>]*>(.*?)</pre>", body, re.S)
html = m.group(1) if m else body

# extract XHRs
m2 = re.search(r"<pre[^>]*id=['\"]XHR_CAPTURE['\"][^>]*>(.*?)</pre>", body, re.S)
captured = []
if m2:
    try:
        captured = json.loads(m2.group(1))
    except Exception:
        try:
            captured = json.loads(m2.group(1).encode('utf-8').decode('unicode_escape'))
        except Exception:
            captured = []

# detect total
m_total = re.search(r'Total number of projects\s*:\s*(\d+)', html, re.I)
total = int(m_total.group(1)) if m_total else None

# find project ids and sample
soup = BeautifulSoup(html, 'lxml')
markers = soup.find_all(string=re.compile(r'Project ID\s*(\d+)', re.I))
ids = []
samples = []
for marker in markers[:20]:
    m_id = re.search(r'Project ID\s*(\d+)', marker, re.I)
    pid = m_id.group(1).strip() if m_id else None
    if not pid:
        continue
    # try to find title nearby
    parent = marker.parent
    container = None
    for _ in range(8):
        if parent is None:
            break
        text = parent.get_text('\n', strip=True)
        if pid and pid in text and len(text) > 40:
            container = parent
            break
        parent = parent.parent
    title = ''
    if container:
        # find heading-like tag
        for t in ['h1','h2','h3','h4','strong','b']:
            tag = container.find(t)
            if tag:
                ttxt = tag.get_text('\n', strip=True)
                if ttxt and 'Project ID' not in ttxt and len(ttxt) > 3:
                    title = ttxt
                    break
        if not title:
            lines = [ln.strip() for ln in container.get_text('\n').split('\n') if ln.strip()]
            lines = [ln for ln in lines if not re.match(r'^(Faculty|Project Location|Language|Preferred start date|Project ID)', ln, re.I)]
            if lines:
                title = lines[0]
    ids.append(pid)
    samples.append({'id': pid, 'title': title})

print('\nVerification results:')
print(' total (from page):', total)
print(' parsed project markers (count):', len(ids))
print(' sample records:')
print(json.dumps(samples[:10], indent=2, ensure_ascii=False))
print('\nCaptured XHRs:')
print(json.dumps(captured, indent=2))
