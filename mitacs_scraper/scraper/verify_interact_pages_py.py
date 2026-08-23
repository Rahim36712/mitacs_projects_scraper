import time, json, re
from bs4 import BeautifulSoup
from scrapling.fetchers import DynamicFetcher

keyword = 'biomedical'
url = 'https://globalink.mitacs.ca/#/student/application/projects'

page_setup_js = """
() => { window._captured_xhr = []; }
"""

print('Running Python-driven page_action verification for keyword:', keyword)

def page_action(page):
    try:
        # find candidate inputs
        inputs = page.query_selector_all('input')
        target = None
        for inp in inputs:
            try:
                ph = (inp.get_attribute('placeholder') or '').lower()
            except Exception:
                ph = ''
            if 'keyword' in ph or 'keyword search' in ph:
                target = inp
                break
        if not target and inputs:
            # fallback: first visible input inside filter panel if possible
            for inp in inputs:
                try:
                    if inp.is_visible():
                        target = inp
                        break
                except Exception:
                    target = inp
                    break
        if target:
            try:
                target.click()
                page.keyboard.type(keyword, delay=50)
            except Exception:
                try:
                    # fallback: set via evaluate
                    page.evaluate("(k)=>{ const input = Array.from(document.querySelectorAll('input')).find(i=> (i.placeholder||'').toLowerCase().includes('keyword')); if(input){ input.value=k; input.dispatchEvent(new Event('input',{bubbles:true, composed:true})); input.dispatchEvent(new Event('change',{bubbles:true})); } }", keyword)
                except Exception:
                    pass
        # click search button
        btn = None
        for b in page.query_selector_all('button'):
            try:
                txt = (b.inner_text() or '').strip().lower()
            except Exception:
                txt = ''
            if 'search and filter' in txt or txt == 'search' or txt.startswith('search'):
                btn = b
                break
        if btn:
            try:
                btn.click()
            except Exception:
                try:
                    page.evaluate("() => { const b = Array.from(document.querySelectorAll('button')).find(x=> (x.textContent||'').toLowerCase().includes('search')); if(b) b.click(); }")
                except Exception:
                    pass
        # wait for results
        try:
            page.wait_for_load_state('networkidle', timeout=10000)
        except Exception:
            page.wait_for_timeout(1500)

        def collect():
            try:
                entries = page.evaluate('''() => {
                    const out = [];
                    const candidates = Array.from(document.querySelectorAll('div, li, article'));
                    const seen = new Set();
                    for(const el of candidates){
                        const txt = (el.innerText||'').trim();
                        if(!txt) continue;
                        if(txt.toLowerCase().indexOf('project id')===-1) continue;
                        if(!(txt.toLowerCase().indexOf('view detail')!==-1 || txt.toLowerCase().indexOf('preferred start date')!==-1 || txt.toLowerCase().indexOf('language')!==-1 || txt.toLowerCase().indexOf('apply')!==-1)) continue;
                        const key = txt.slice(0,400);
                        if(seen.has(key)) continue; seen.add(key);
                        out.push(el.outerHTML);
                    }
                    return out;
                }''')
                return entries
            except Exception:
                return []

        pages = []
        p1 = collect()
        pages.append(p1)
        # click numeric 2 if available
        clicked = False
        try:
            for b in page.query_selector_all('button'):
                try:
                    t = (b.inner_text() or '').strip()
                except Exception:
                    t = ''
                if t == '2':
                    try:
                        b.click(); clicked=True; break
                    except Exception:
                        pass
        except Exception:
            clicked = False
        if not clicked:
            # try next
            try:
                nxt = page.query_selector('.p-paginator-next')
                if not nxt:
                    for b in page.query_selector_all('button'):
                        try:
                            aria = b.get_attribute('aria-label') or ''
                        except Exception:
                            aria = ''
                        try:
                            txt = (b.inner_text() or '').strip()
                        except Exception:
                            txt = ''
                        if 'next' in aria.lower() or txt == '>' or txt.lower().startswith('next'):
                            try:
                                b.click(); clicked=True; break
                            except Exception:
                                pass
            except Exception:
                clicked = False
        if clicked:
            try:
                page.wait_for_load_state('networkidle', timeout=8000)
            except Exception:
                page.wait_for_timeout(1200)
            p2 = collect()
            pages.append(p2)
        # store results in page DOM for Python to read
        try:
            joined = '\n<!--PAGE_DELIM-->\n'.join([p.join('\n<!--ENTRY_DELIM-->\n') for p in pages])
            page.evaluate('(v)=>{const pre=document.createElement(\'pre\');pre.id=\'SCRAP_RESULT\';pre.style.display=\'none\';pre.textContent=v;document.body.appendChild(pre);}', joined)
        except Exception:
            pass
    except Exception as e:
        try:
            page.wait_for_timeout(1200)
        except Exception:
            pass

resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=180000, wait=500, page_setup=lambda p: p.evaluate(page_setup_js), page_action=page_action)
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

# parse first page entries (up to 11)

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
    desc_parts = []
    for p in soup.find_all('p'):
        t = p.get_text('\n', strip=True)
        if t: desc_parts.append(t)
    if not desc_parts:
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
    print(first_page_records[0]['description'][:4000])
else:
    print('\nNo records parsed on first page')
