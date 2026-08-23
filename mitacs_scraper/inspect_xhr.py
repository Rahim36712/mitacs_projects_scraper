from scrapling.fetchers import DynamicFetcher

url = 'https://globalink.mitacs.ca/#/student/application/projects'
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=30000, wait=1000)
print('Status:', getattr(resp,'status',None))
print('URL:', getattr(resp,'url',None))
print('Captured XHR count:', len(getattr(resp,'captured_xhr', []) ))
for i, c in enumerate(getattr(resp,'captured_xhr', [])[:20]):
    try:
        print(i, c['method'], c['url'])
    except Exception:
        print(i, c)

# Try to find if JSON payloads are present via resp.json()
try:
    js = resp.json()
    print('resp.json() returned keys (if dict):', list(js.keys()) if isinstance(js, dict) else type(js))
except Exception as e:
    print('resp.json() error:', e)

# Try to see if body contains 'projects' word
body = getattr(resp, 'body', b'')
print('body contains projects?', b'project' in body.lower())
