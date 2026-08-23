from scrapling.fetchers import DynamicFetcher

url = 'https://globalink.mitacs.ca/#/student/application/projects'
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=60000, wait=2000)
print('Status:', getattr(resp,'status',None))
print('URL:', getattr(resp,'url',None))
hist = getattr(resp,'history', None)
print('History type:', type(hist))
try:
    for i, h in enumerate(hist[:80]):
        try:
            print(i, getattr(h,'method',None), getattr(h,'url',None), getattr(h,'status',None))
        except Exception as e:
            print('history item error', e)
except Exception as e:
    print('No history or error:', e)
