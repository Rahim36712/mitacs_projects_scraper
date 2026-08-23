from scrapling.fetchers import DynamicFetcher
import re

url = 'https://globalink.mitacs.ca/#/student/application/projects'
PAGE_SETUP = ("""
() => {
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
  const input = Array.from(document.querySelectorAll('input')).find(i=> (i.placeholder||'').toLowerCase().includes('keyword'));
  if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); }
  const btn = Array.from(document.querySelectorAll('button')).find(b=> b.textContent && b.textContent.toLowerCase().includes('search'));
  if(btn) btn.click();
  return (async ()=>{ await new Promise(r=>setTimeout(r,1800));
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

print('Running dynamic fetch with page_setup to capture XHR (debug)')
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=500, page_setup=lambda page: page.evaluate(PAGE_SETUP), page_action=lambda page: page.evaluate(PAGE_ACTION))
body = getattr(resp,'body',b'').decode('utf-8', errors='ignore')
print('Body length:', len(body))
start = body.find('<pre id="SCRAP_XHR"')
print('pre index:', start)
print('body snippet near pre:\n', body[start-200:start+200])
m = re.search(r"<pre[^>]*id=['\"]SCRAP_XHR['\"][^>]*>(.*?)</pre>", body, re.S)
if not m:
    print('No SCRAP_XHR element found')
else:
    data = m.group(1)
    print('SCRAP_XHR raw repr:', repr(data[:500]))
    print('Length:', len(data))
