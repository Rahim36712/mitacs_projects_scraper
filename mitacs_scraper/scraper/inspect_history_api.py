from scrapling.fetchers import DynamicFetcher
import json
import re

url = 'https://globalink.mitacs.ca/#/student/application/projects'
keyword = 'biomedical'

page_setup = lambda page: page.evaluate(f"() => {{ window._mitacs_keyword = {repr(keyword)}; }}")
PAGE_ACTION = '''
() => {
  try{
    const input = Array.from(document.querySelectorAll('input')).find(i=> (i.placeholder||'').toLowerCase().includes('keyword'));
    if(input){ input.value = window._mitacs_keyword || ''; input.dispatchEvent(new Event('input', {bubbles:true})); }
  }catch(e){}
  try{ const btn = Array.from(document.querySelectorAll('button')).find(b=> b.textContent && b.textContent.toLowerCase().includes('search')); if(btn) btn.click(); }catch(e){}
  return (async ()=>{ await new Promise(r=>setTimeout(r,1500)); return true; })();
}
'''

print('Fetching page and capturing history...')
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=500, page_setup=page_setup, page_action=lambda page: page.evaluate(PAGE_ACTION))
print('Status:', getattr(resp,'status',None))
hist = getattr(resp, 'history', [])
print('History entries:', len(hist))

candidates = []
for h in hist:
    try:
        u = getattr(h, 'url', None) or h.get('url')
    except Exception:
        u = None
    try:
        method = getattr(h, 'method', None) or h.get('method')
    except Exception:
        method = None
    try:
        status = getattr(h, 'status', None) or h.get('status')
    except Exception:
        status = None
    if u and re.search(r'/api|/projects|search|query|application/projects|graphql', u, re.I):
        candidates.append((method, u, status))

print('\nCandidate API-ish requests:')
for c in candidates[:50]:
    print('-', c)

# Attempt to print any captured_xhr if available
cx = getattr(resp, 'captured_xhr', None)
if cx:
    print('\ncaptured_xhr entries:', len(cx))
    for i, e in enumerate(cx[:20]):
        print(i, e)
else:
    print('\nNo captured_xhr attribute or it is empty')

# Try to find any JSON-like responses in history
print('\nLooking for JSON responses in history...')
for h in hist[:200]:
    try:
        if getattr(h, 'headers', None):
            htype = h.headers.get('content-type') or h.headers.get('Content-Type')
            if htype and 'application/json' in htype:
                print('JSON response:', getattr(h,'url',None), 'status', getattr(h,'status',None))
    except Exception:
        pass

print('\nDone')
