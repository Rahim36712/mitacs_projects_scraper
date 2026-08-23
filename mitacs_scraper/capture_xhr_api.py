from scrapling.fetchers import DynamicFetcher
import re
import json

url = 'https://globalink.mitacs.ca/#/student/application/projects'

PAGE_SETUP = ("""
() => {
  // Install global capture array and monkey-patch fetch/XHR before navigation
  window._captured_xhr = [];
  (function(){
    const origFetch = window.fetch;
    window.fetch = function(...args){ try{ window._captured_xhr.push({type:'fetch', url: args[0]}); }catch(e){} return origFetch.apply(this,args); };
    const XHRproto = XMLHttpRequest.prototype;
    const origOpen = XHRproto.open;
    XHRproto.open = function(method, url){ try{ this._loggedUrl = url; }catch(e){} return origOpen.apply(this, arguments); };
    const origSend = XHRproto.send;
    XHRproto.send = function(){ try{ window._captured_xhr.push({type:'xhr', url: this._loggedUrl}); }catch(e){} return origSend.apply(this, arguments); };
  })();
}
""")

PAGE_ACTION = ("""
() => {
  // set keyword input and click search
  const input = Array.from(document.querySelectorAll('input')).find(i=> (i.placeholder||'').toLowerCase().includes('keyword'));
  if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); }
  const btn = Array.from(document.querySelectorAll('button')).find(b=> b.textContent && b.textContent.toLowerCase().includes('search'));
  if(btn) btn.click();
  return (async ()=>{ await new Promise(r=>setTimeout(r,1500));
    // expose captured XHR in a pre element
    try{
      const pre = document.createElement('pre');
      pre.id = 'SCRAP_XHR';
      pre.style.display = 'none';
      pre.textContent = JSON.stringify(window._captured_xhr);
      document.body.appendChild(pre);
    }catch(e){ }
    return true;
  })();
}
""")

print('Running dynamic fetch with page_setup to capture XHR')
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=500, page_setup=lambda page: page.evaluate(PAGE_SETUP), page_action=lambda page: page.evaluate(PAGE_ACTION))
body = getattr(resp,'body',b'').decode('utf-8', errors='ignore')
m = re.search(r"<pre[^>]*id=['\"]SCRAP_XHR['\"][^>]*>(.*?)</pre>", body, re.S)
if not m:
    print('No SCRAP_XHR element found')
    print('Response body length:', len(body))
else:
    data = m.group(1)
    try:
        arr = json.loads(data)
        print('Captured XHR count:', len(arr))
        for i, it in enumerate(arr[:30]):
            print(i, it)
    except Exception as e:
        print('Failed to parse SCRAP_XHR JSON:', e)
        print('raw:', data[:1000])
