from scrapling.fetchers import DynamicFetcher
from bs4 import BeautifulSoup

url = 'https://globalink.mitacs.ca/#/student/application/projects'
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=2000, page_action=lambda page: page.evaluate("() => { const input = Array.from(document.querySelectorAll('input')).find(i => (i.placeholder||'').toLowerCase().includes('keyword')); if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); } var btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.toLowerCase().includes('search')); if(btn) btn.click(); }"))
body = getattr(resp,'body',b'')
s = body.decode('utf-8', errors='ignore').lower()
print('mat-paginator in body?', 'mat-paginator' in s)
print('pagination in body?', 'pagination' in s)
print('next in body?', 'next' in s)
print('show more in body?', 'show more' in s)
# check for 'page' or 'page-index'
print("page keywords present:", any(k in s for k in ['page=', 'pageindex', 'paginator', 'page-size', 'items-per-page']))
