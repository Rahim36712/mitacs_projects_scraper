from scrapling.fetchers import DynamicFetcher

url = 'https://globalink.mitacs.ca/#/student/application/projects'
print('Calling DynamicFetcher.fetch...')
resp = DynamicFetcher.fetch(url, headless=True, load_dom=True, network_idle=True, timeout=30000, wait=500)
print('repr:', repr(resp))
print('dir:', [a for a in dir(resp) if not a.startswith('_')])
# Try to dump common attributes
for attr in ('text','content','body','html','url','status_code','status','headers','raw'):
    try:
        print(attr, '->', getattr(resp, attr))
    except Exception as e:
        print(attr, '->', 'ERROR', e)
