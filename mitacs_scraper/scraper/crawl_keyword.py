"""
Crawl projects for a given keyword and export CSV with columns:
id,title,description,start_date,language

This script uses Scrapling DynamicFetcher to render the SPA, set the keyword in the filter,
click Search, walk the paginator, collect page HTML, and then parse project blocks.
"""
from typing import List, Dict
import re
import csv
import json
from bs4 import BeautifulSoup
from scrapling.fetchers import DynamicFetcher
from mitacs_scraper import config


def normalize_text(s: str) -> str:
    if s is None:
        return ""
    return " ".join(s.split()).strip()


def collect_pages_for_keyword(keyword: str, max_pages: int = 0, use_typing: bool = True, return_capture: bool = False):
    """Render the listing page, set the keyword filter, click Search and collect pages by clicking paginator.
    Returns list of page HTML strings (one per page collected). If max_pages>0, limit to that many pages.
    If use_typing=True, the page_action will simulate real typing/clicks using Playwright page methods for better compatibility with Angular bindings.
    """
    url = 'https://globalink.mitacs.ca/#/student/application/projects'

    # Prepare a page_setup that installs XHR/fetch capture and optionally max_pages
    capture_setup_js = '''() => {
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
}'''
    if max_pages and max_pages > 0:
        PAGE_SETUP = f"() => {{ window._mitacs_max_pages = {int(max_pages)}; }}"
        page_setup = lambda page: (page.evaluate(capture_setup_js), page.evaluate(PAGE_SETUP))
    else:
        page_setup = lambda page: page.evaluate(capture_setup_js)

    if use_typing:
        def page_action(page):
            try:
                # find the keyword input by placeholder
                inputs = page.query_selector_all('input')
                target = None
                for inp in inputs:
                    try:
                        ph = (inp.get_attribute('placeholder') or '')
                    except Exception:
                        ph = ''
                    if 'keyword' in ph.lower() or 'keyword search' in ph.lower():
                        target = inp
                        break
                if not target and inputs:
                    # fallback: first input in the filter panel
                    target = inputs[0]
                # Try robust DOM-based input set via evaluate (target by label), then click Search
                try:
                    js = '''(() => {
  const KEY = %s;
  function findKeywordInput(){
    // look for labelled field 'Keyword search'
    const labels = Array.from(document.querySelectorAll('.input-label, label, .header-container'));
    const kwLabel = labels.find(e => /Keyword search/i.test(e.textContent || ''));
    if(kwLabel){
      // search within nearby DOM
      let input = kwLabel.closest('div') ? kwLabel.closest('div').querySelector('input') : null;
      if(!input) input = kwLabel.parentElement ? kwLabel.parentElement.querySelector('input') : null;
      if(input) return input;
    }
    // fallback: first visible input
    const inputs = Array.from(document.querySelectorAll('input'));
    for(const i of inputs){ if(i.offsetParent !== null) return i; }
    return null;
  }
  const input = findKeywordInput();
  if(!input) return false;
  input.focus();
  input.value = KEY;
  input.dispatchEvent(new Event('input', {bubbles:true, composed:true}));
  input.dispatchEvent(new Event('change', {bubbles:true}));
  // find and click the search button
  const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent||'').toLowerCase().includes('search and filter') || (b.textContent||'').toLowerCase().includes('search'));
  if(btn){ btn.click(); }
  // also try pressing Enter on the input
  try{ input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true})); input.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', bubbles:true})); }catch(e){}
  return true;
})()'''
                    js = js % (json.dumps(str(keyword)))
                    page.evaluate(js)
                except Exception:
                    try:
                        # fallback: attempt typing into target
                        if target:
                            target.click()
                            page.keyboard.type(str(keyword), delay=50)
                    except Exception:
                        pass
                # wait for results to load
                try:
                    page.wait_for_load_state('networkidle', timeout=10000)
                except Exception:
                    page.wait_for_timeout(1200)
                # now paginate by clicking next until disabled or max reached
                collected = []
                def push():
                    try:
                        # Extract the project-list container HTML, not the full document
                        html = page.evaluate('''() => {
  // find heading that says 'Project List' and return its nearest ancestor container
  const heading = Array.from(document.querySelectorAll('h1,h2,h3,h4,div,span')).find(e => /Project List/i.test((e.textContent||'')));
  let container = null;
  if(heading){ container = heading.closest('div'); }
  if(!container){
    // try to find by aria-label or known class names
    container = document.querySelector('.project-list') || document.querySelector('.p-grid') || document.querySelector('body');
  }
  return container ? container.innerHTML : document.documentElement.innerHTML;
}''')
                        collected.append(str(html))
                    except Exception:
                        try:
                            collected.append(page.evaluate('() => document.documentElement.innerHTML'))
                        except Exception:
                            collected.append('')
                push()
                for _ in range(100):
                    # find next control
                    nxt = page.query_selector('.p-paginator-next')
                    if not nxt:
                        # try aria labelled next buttons
                        nxt = None
                        for b in page.query_selector_all('button'):
                            try:
                                aria = b.get_attribute('aria-label') or ''
                                txt = (b.inner_text() or '').strip().lower()
                            except Exception:
                                aria = ''
                                txt = ''
                            if 'next' in aria.lower() or txt == '>' or txt.startswith('>') or 'next' in txt:
                                nxt = b
                                break
                    if not nxt:
                        break
                    try:
                        disabled = False
                        cls = (nxt.get_attribute('class') or '')
                        if 'p-disabled' in cls or nxt.get_attribute('disabled') is not None:
                            disabled = True
                    except Exception:
                        disabled = False
                    if disabled:
                        break
                    try:
                        nxt.click()
                    except Exception:
                        break
                    try:
                        page.wait_for_load_state('networkidle', timeout=8000)
                    except Exception:
                        page.wait_for_timeout(900)
                    push()
                    # respect max pages injected via page_setup
                    if max_pages and len(collected) >= max_pages:
                        break
                # attach collected into a hidden pre element so the fetched response contains it
                try:
                    joined = '\n<!--PAGE_DELIM-->\n'.join(collected)
                    page.evaluate("(v)=>{const pre=document.createElement('pre');pre.id='SCRAP_RESULT';pre.style.display='none';pre.textContent=v;document.body.appendChild(pre);} ", joined)
                    # also export captured xhrs if any
                    try:
                        page.evaluate("() => { const pre = document.createElement('pre'); pre.id='XHR_CAPTURE'; pre.style.display='none'; pre.textContent = JSON.stringify(window._captured_xhr || []); document.body.appendChild(pre); }")
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                try:
                    page.wait_for_timeout(1200)
                except Exception:
                    pass
        resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=180000, wait=500, page_setup=page_setup, page_action=page_action)
    else:
        # fallback to JS-eval based action (less robust)
        PAGE_ACTION = f"""
        () => {{
          window._collected = [];
          function push(){{ try{{ window._collected.push(document.querySelector('body').innerHTML); }}catch(e){{ window._collected.push(document.documentElement.innerHTML); }} }}

          // set keyword input: find the filter panel by its heading then the input inside it
          try{{
            const panels = Array.from(document.querySelectorAll('div'));
            let panel = panels.find(d => d.textContent && d.textContent.includes('Search and Filter Globalink Projects')) || document;
            const input = panel.querySelector('input') || Array.from(document.querySelectorAll('input')).find(i=> (i.placeholder||'').toLowerCase().includes('keyword'));
            if(input){{ input.value = {json.dumps(keyword)}; input.dispatchEvent(new Event('input', {{bubbles:true}})); }}
          }}catch(e){{}}

          // click Search and Filter button specifically
          try{{
            const btn = Array.from(document.querySelectorAll('button')).find(b=> b.textContent && b.textContent.toLowerCase().includes('search and filter')) || Array.from(document.querySelectorAll('button')).find(b=> b.textContent && b.textContent.toLowerCase().includes('search'));
            if(btn) btn.click();
          }}catch(e){{}}

          const wait = (ms)=> new Promise(r=>setTimeout(r, ms));
          return (async ()=>{{
            await wait(1400);
            push();
            for(let i=0;i<100;i++){{
              // prefer PrimeNG paginator next button
              let nxt = document.querySelector('.p-paginator-next') || Array.from(document.querySelectorAll('button')).find(b=> (b.getAttribute('aria-label')||'').toLowerCase().includes('next'));
              if(!nxt) break;
              // if disabled, stop
              if(nxt.disabled || (nxt.className||'').toLowerCase().includes('p-disabled')) break;
              try{{ nxt.click(); }}catch(e){{ break; }}
              await wait(1000);
              push();
              // optional limit via injected variable
              if (typeof window._mitacs_max_pages !== 'undefined' && window._collected.length >= window._mitacs_max_pages) break;
            }}
            // place collected pages into hidden pre element
            const pre = document.createElement('pre'); pre.id='SCRAP_RESULT'; pre.style.display='none'; pre.textContent = window._collected.join('\n<!--PAGE_DELIM-->\n'); document.body.appendChild(pre);
            try{ const pre2 = document.createElement('pre'); pre2.id='XHR_CAPTURE'; pre2.style.display='none'; pre2.textContent = JSON.stringify(window._captured_xhr || []); document.body.appendChild(pre2); }catch(e){}
          }})();
        }}
        """        resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=180000, wait=500, page_setup=page_setup, page_action=lambda page: page.evaluate(PAGE_ACTION))

    body = getattr(resp, 'body', b'').decode('utf-8', errors='ignore')
    m = re.search(r"<pre[^>]*id=['\"]SCRAP_RESULT['\"][^>]*>(.*?)</pre>", body, re.S)
    pages = []
    if not m:
        # fallback single page
        pages = [body]
    else:
        data = m.group(1)
        pages = data.split('\n<!--PAGE_DELIM-->\n')
    # try to capture XHR_CAPTURE if present
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
    if return_capture:
        return pages, captured
    return pages


def parse_projects_from_page(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, 'lxml')
    records = []

    # Find project ID markers and use nearest block container
    markers = soup.find_all(string=re.compile(r'Project ID\s*(\d+)', re.I))
    for marker in markers:
        # get the numeric id
        m_id = re.search(r'Project ID\s*(\d+)', marker, re.I)
        pid = m_id.group(1).strip() if m_id else None
        # find a reasonable container: prefer ancestor with many descendants
        parent = marker.parent
        container = None
        for _ in range(8):
            if parent is None:
                break
            text = parent.get_text('\n', strip=True)
            if pid and pid in text and len(text) > 60:
                container = parent
                break
            parent = parent.parent
        if container is None:
            continue

        rec = {'id': pid, 'title': '', 'description': '', 'start_date': '', 'language': ''}

        # Title: look for bold/strong/h tags inside container
        title = None
        for tag in ['h1','h2','h3','h4','strong','b']:
            ttag = container.find(tag)
            if ttag:
                ttxt = ttag.get_text('\n', strip=True)
                # ignore cases where title is same as 'Project ID'
                if ttxt and 'Project ID' not in ttxt and len(ttxt) > 3:
                    title = ttxt
                    break
        if not title:
            # some titles are the first large text node before 'View Detail'
            lines = [ln.strip() for ln in container.get_text('\n').split('\n') if ln.strip()]
            # remove known label lines
            lines = [ln for ln in lines if not re.match(r'^(Faculty|Project Location|Language|Preferred start date|Project ID)', ln, re.I)]
            if lines:
                # first non-label line could be title
                title = lines[0]
        rec['title'] = normalize_text(title or '')

        # Description: prefer first <p> with substantial length inside container
        desc = ''
        for p in container.find_all('p'):
            txt = p.get_text('\n', strip=True)
            if len(txt) >= 40:
                desc = txt
                break
        if not desc:
            # fallback: take text lines after the title
            all_lines = [ln.strip() for ln in container.get_text('\n').split('\n') if ln.strip()]
            if title and title in all_lines:
                idx = all_lines.index(title)
                # take next few lines that are not labels
                candidate_lines = []
                for ln in all_lines[idx+1:idx+6]:
                    if re.match(r'^(Faculty|Project Location|Language|Preferred start date|Project ID)', ln, re.I):
                        break
                    candidate_lines.append(ln)
                desc = ' '.join(candidate_lines)
            else:
                # as last resort, take the biggest contiguous block
                blocks = re.split(r'\n{2,}', container.get_text('\n'))
                blocks = [b.strip() for b in blocks if len(b.strip())>40]
                if blocks:
                    desc = blocks[0]
        rec['description'] = normalize_text(desc or '')

        # start_date and language: try to extract from container text using labels
        ctext = container.get_text('\n', strip=True)
        m = re.search(r'Preferred start date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})', ctext, re.I)
        if m:
            rec['start_date'] = m.group(1)
        else:
            m = re.search(r'Preferred start date:\s*([0-9]{4}-[0-9]{2})', ctext, re.I)
            if m:
                rec['start_date'] = m.group(1)

        m = re.search(r'Language:\s*([A-Za-z]+)', ctext, re.I)
        if m:
            rec['language'] = m.group(1).strip()

        records.append(rec)
    return records


def crawl_keyword_to_csv(keyword: str, out_csv: str, max_pages: int = 0) -> int:
    pages = collect_pages_for_keyword(keyword, max_pages=max_pages)
    all_records = []
    for p in pages:
        recs = parse_projects_from_page(p)
        all_records.extend(recs)

    # Deduplicate by id (keep first occurrence)
    seen = set()
    rows = []
    for r in all_records:
        pid = r.get('id') or None
        if pid in seen:
            continue
        seen.add(pid)
        rows.append({
            'id': r.get('id') or '',
            'title': r.get('title') or '',
            'description': r.get('description') or '',
            'start_date': r.get('start_date') or '',
            'language': r.get('language') or '',
        })

    # write CSV
    fieldnames = ['id','title','description','start_date','language']
    with open(out_csv, 'w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return len(rows)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(prog='crawl_keyword')
    parser.add_argument('keyword')
    parser.add_argument('--out', default=str(config.OUTPUT_CSV))
    parser.add_argument('--max-pages', type=int, default=0, help='Optional limit to pages to collect (0 = all)')
    args = parser.parse_args()
    count = crawl_keyword_to_csv(args.keyword, args.out, max_pages=args.max_pages)
    print(f'Wrote {count} records to {args.out}')
