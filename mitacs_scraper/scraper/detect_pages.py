from scrapling.fetchers import DynamicFetcher
import re

url = 'https://globalink.mitacs.ca/#/student/application/projects'

PAGE_ACTION = '''
() => {
  // set keyword
  try{
    const input = Array.from(document.querySelectorAll('input')).find(i=> (i.placeholder||'').toLowerCase().includes('keyword'));
    if(input){ input.value = window._mitacs_keyword || ''; input.dispatchEvent(new Event('input', {bubbles:true})); }
  }catch(e){}
  // click search
  try{
    const btn = Array.from(document.querySelectorAll('button')).find(b=> b.textContent && b.textContent.toLowerCase().includes('search'));
    if(btn) btn.click();
  }catch(e){}
  const wait = (ms)=> new Promise(r=>setTimeout(r, ms));
  return (async ()=>{
    await wait(1000);
    // try to find paginator page numbers
    let pages = 1;
    try{
      const pageButtons = Array.from(document.querySelectorAll('.p-paginator-page'))
        .map(b=> parseInt((b.textContent||'').trim()))
        .filter(n=> !isNaN(n));
      if(pageButtons.length) pages = Math.max(...pageButtons);
      else{
        // fallback: check for aria-labelled page numbers inside paginator
        const paginator = document.querySelector('.p-paginator');
        if(paginator){
          const txt = paginator.textContent || '';
          const matches = txt.match(/\b(\d+)\b/g);
          if(matches) pages = Math.max(...matches.map(m=>parseInt(m)));
        }
      }
    }catch(e){}
    const pre = document.createElement('pre'); pre.id='MITACS_TOTAL_PAGES'; pre.style.display='none'; pre.textContent = String(pages); document.body.appendChild(pre);
  })();
}
'''

def detect_total_pages(keyword: str) -> int:
    # pass keyword via page_setup variable
    page_setup = lambda page: page.evaluate(f"() => {{ window._mitacs_keyword = {repr(keyword)}; }}")
    resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=500, page_setup=page_setup, page_action=lambda page: page.evaluate(PAGE_ACTION))
    body = getattr(resp, 'body', b'').decode('utf-8', errors='ignore')

    # Try to read explicit "Total number of projects: N" shown on page
    m_total = re.search(r'Total number of projects\s*:\s*(\d+)', body, re.I)
    if m_total:
        total = int(m_total.group(1))
        # count items on the first page by Project ID occurrences
        per_page = max(1, len(re.findall(r'Project ID\s*\d+', body)))
        if per_page <= 1:
            per_page = 10
        import math
        return math.ceil(total / per_page)

    # fallback: look for the injected pre element
    m = re.search(r"<pre[^>]*id=['\"]MITACS_TOTAL_PAGES['\"][^>]*>(.*?)</pre>", body, re.S)
    if not m:
        return 1
    try:
        return int(m.group(1).strip())
    except Exception:
        return 1

if __name__ == '__main__':
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else ''
    pages = detect_total_pages(kw)
    print(pages)
