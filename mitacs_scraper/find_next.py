from scrapling.fetchers import DynamicFetcher
from bs4 import BeautifulSoup

url = 'https://globalink.mitacs.ca/#/student/application/projects'
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=2000, page_action=lambda page: page.evaluate("() => { const input = Array.from(document.querySelectorAll('input')).find(i => (i.placeholder||'').toLowerCase().includes('keyword')); if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); } var btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.toLowerCase().includes('search')); if(btn) btn.click(); }"))
body = getattr(resp,'body',b'')
soup = BeautifulSoup(body, 'lxml')
for el in soup.find_all(string=lambda s: s and 'next' in s.lower()):
    parent = el.parent
    print('TEXT:', el.strip())
    print('TAG:', parent.name)
    print('CLASS:', parent.get('class'))
    print('ATTRS:', parent.attrs)
    print('OUTER HTML SNIPPET:', parent.prettify()[:400])
    print('---')
