from scrapling.fetchers import DynamicFetcher
from bs4 import BeautifulSoup

url = 'https://globalink.mitacs.ca/#/student/application/projects'
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=2000, page_action=lambda page: page.evaluate("() => { const input = Array.from(document.querySelectorAll('input')).find(i => (i.placeholder||'').toLowerCase().includes('keyword')); if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); } var btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.toLowerCase().includes('search')); if(btn) btn.click(); }"))
body = getattr(resp,'body',b'')
soup = BeautifulSoup(body.decode('utf-8',errors='ignore'),'lxml')
els = soup.find_all(class_=lambda c: c and 'p-paginator' in ' '.join(c))
print('Found p-paginator elements:', len(els))
for e in els:
    print('outer html snippet:', e.prettify()[:1200])
    print('---')
