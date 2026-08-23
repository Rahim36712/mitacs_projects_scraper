import json, re
from scrapling.fetchers import DynamicFetcher

keyword = 'biomedical'
url = 'https://globalink.mitacs.ca/#/student/application/projects'

page_setup_js = """
() => { window._captured_xhr = []; }
"""

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
  if(input){ input.focus(); input.value = KEY; input.dispatchEvent(new Event('input',{bubbles:true, composed:true})); input.dispatchEvent(new Event('change',{bubbles:true})); try{ input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter', bubbles:true})); input.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter', bubbles:true})); }catch(e){} }
  const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent||'').toLowerCase().includes('search and filter') || (b.textContent||'').toLowerCase().includes('search'));
  if(btn){ try{ btn.click(); }catch(e){} }
  const wait = (ms)=> new Promise(r=>setTimeout(r, ms));
  return (async ()=>{
    await wait(1600);
    await wait(800);
    // find all nodes that contain 'Project ID' text
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
    const nodes = [];
    while(walker.nextNode()){
      const txt = walker.currentNode.nodeValue || '';
      if(/Project ID\s*\d+/i.test(txt)) nodes.push(walker.currentNode);
    }
    const results = [];
    for(const n of nodes){
      try{
        // climb to a container div
        let el = n.parentElement;
        for(let i=0;i<8 && el; i++){
          const text = el.innerText || '';
          if(/Project ID\s*\d+/i.test(text) && /Preferred start date|Language|View Detail|Apply/i.test(text)){
            // extract title
            let title = '';
            const h = el.querySelector('h1,h2,h3,h4');
            if(h) title = h.innerText.trim();
            if(!title){ const bold = el.querySelector('strong,b'); if(bold) title = bold.innerText.trim(); }
            if(!title){ // fallback: first non-label line
              const lines = el.innerText.split('\n').map(s=>s.trim()).filter(s=>s);
              const lines2 = lines.filter(l=>!/^(Faculty|Project Location|Language|Preferred start date|Project ID)/i.test(l));
              if(lines2.length) title = lines2[0];
            }
            // description: collect all <p> texts
            let desc = '';
            const ps = el.querySelectorAll('p');
            if(ps && ps.length){ desc = Array.from(ps).map(p=>p.innerText.trim()).filter(Boolean).join('\n'); }
            if(!desc){ // fallback: take many lines after title
              const lines = el.innerText.split('\n').map(s=>s.trim()).filter(s=>s);
              let start = 0;
              for(let i=0;i<lines.length;i++){ if(lines[i]===title){ start=i+1; break; } }
              const out = [];
              for(let i=start;i<Math.min(lines.length,start+30);i++){
                if(/^(Faculty|Project Location|Language|Preferred start date|Project ID)/i.test(lines[i])) break;
                out.push(lines[i]);
              }
              desc = out.join('\n');
            }
            const mid = (text.match(/Project ID\s*(\d+)/i) || [null,''])[1] || '';
            results.push({id: mid, title: title.trim(), description: desc.trim()});
            break;
          }
          el = el.parentElement;
        }
      }catch(e){}
    }
    const pre = document.createElement('pre'); pre.id='SCRAP_JSON'; pre.style.display='none'; pre.textContent = JSON.stringify(results); document.body.appendChild(pre);
  })();
}
""" % (json.dumps(keyword))

print('Running eval-based extraction for keyword:', keyword)
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=180000, wait=500, page_setup=lambda p: p.evaluate(page_setup_js), page_action=lambda p: p.evaluate(page_action_js))
body = getattr(resp, 'body', b'').decode('utf-8', errors='ignore')

m = re.search(r"<pre[^>]*id=['\"]SCRAP_JSON['\"][^>]*>(.*?)</pre>", body, re.S)
results = []
if m:
    try:
        results = json.loads(m.group(1))
    except Exception:
        results = []

print('Parsed entries count:', len(results))
for r in results[:11]:
    print('-', r.get('id'), r.get('title'))

if results:
    print('\nFull description for first project:')
    print(results[0].get('description'))
else:
    print('\nNo results parsed from evaluation.')
