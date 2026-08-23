from scrapling.fetchers import DynamicFetcher

url = 'https://globalink.mitacs.ca/#/student/application/projects'

# Define a page_action to fill the keyword input and click the search button.
# Use simple DOM scripting to set the input value and click a button that contains 'Search'.

def page_action(page):
    try:
        # Set the keyword value using document-level script
        page.evaluate("() => { const input = Array.from(document.querySelectorAll('input')).find(i => (i.placeholder||'').toLowerCase().includes('keyword')); if(input){ input.value = 'BioMedical'; input.dispatchEvent(new Event('input', {bubbles:true})); } }")
        # Click a button that contains 'Search' in its text
        page.evaluate("() => { const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.toLowerCase().includes('search')); if(btn) btn.click(); }")
    except Exception as e:
        print('page_action error:', e)

resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=2000, page_action=page_action)
print('Status:', getattr(resp,'status',None))
print('URL:', getattr(resp,'url',None))
print('Body length:', len(getattr(resp,'body',b'')))
print('Captured XHR count:', len(getattr(resp,'captured_xhr',[])))
# Save a small snippet
body = getattr(resp,'body',b'')
print('Snippet:', body[:2000])
# Try to call resp.json() if possible
try:
    js = resp.json()
    print('resp.json type:', type(js))
except Exception as e:
    print('resp.json error:', e)

# If captured_xhr are present, print first few
for i,c in enumerate(getattr(resp,'captured_xhr',[])[:10]):
    print('xhr', i, c)
