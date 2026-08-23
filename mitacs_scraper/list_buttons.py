from scrapling.fetchers import DynamicFetcher
import re, json

url = 'https://globalink.mitacs.ca/#/student/application/projects'
PAGE_ACTION = ("""
() => {
  const input = Array.from(document.querySelectorAll('input')).find(i=> (i.placeholder||'').toLowerCase().includes('keyword'));
  if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); }
  const btn = Array.from(document.querySelectorAll('button')).find(b=> b.textContent && b.textContent.toLowerCase().includes('search'));
  if(btn) btn.click();
  return (async ()=>{ await new Promise(r=>setTimeout(r,1200));
    try{
      const items = Array.from(document.querySelectorAll('button')).map(b=>({text: b.textContent, class: b.className, aria: b.getAttribute('aria-label'), disabled: b.disabled}));
      const pre = document.createElement('pre'); pre.id='SCRAP_BUTTONS'; pre.style.display='none'; pre.textContent = JSON.stringify(items); document.body.appendChild(pre);
    }catch(e){ }
    return true;
  })();
}
""")
print('Fetching and listing buttons...')
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=500, page_action=lambda page: page.evaluate(PAGE_ACTION))
body = getattr(resp,'body',b'').decode('utf-8', errors='ignore')
m = re.search(r"<pre[^>]*id=['\"]SCRAP_BUTTONS['\"][^>]*>(.*?)</pre>", body, re.S)
if not m:
    print('No button capture found')
else:
    data = m.group(1)
    try:
        arr = json.loads(data)
        print('Captured', len(arr), 'buttons; sample:')
        for b in arr[:40]:
            print('-', b)
    except Exception as e:
        print('Failed parse', e)
        print('raw:', data[:1000])
