from scrapling.fetchers import DynamicFetcher
from bs4 import BeautifulSoup

url = 'https://globalink.mitacs.ca/#/student/application/projects'
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=2000, page_action=lambda page: page.evaluate("() => { const input = Array.from(document.querySelectorAll('input')).find(i => (i.placeholder||'').toLowerCase().includes('keyword')); if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); } var btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.toLowerCase().includes('search')); if(btn) btn.click(); }"))
body = getattr(resp, 'body', b'')
soup = BeautifulSoup(body, 'lxml')
# Collect candidate links
links = []
for a in soup.find_all('a', href=True):
    href = a['href']
    if 'project' in href.lower() or 'projects' in href.lower():
        links.append(href)

# Also collect elements that look like cards
cards = []
for div in soup.find_all(True):
    cls = ' '.join(div.get('class', []))
    if 'card' in cls.lower() or 'project' in cls.lower() or 'mat-card' in cls.lower():
        text = div.get_text('\n', strip=True)
        if len(text) > 20:
            cards.append(text[:200])

print('Found', len(links), 'links (sample 20):')
for l in links[:20]:
    print('-', l)
print('\nFound', len(cards), 'card-like elements (sample 10):')
for c in cards[:10]:
    print('---')
    print(c)