import inspect, traceback
from scrapling.fetchers import DynamicFetcher

print('DynamicFetcher members:')
print([m for m in dir(DynamicFetcher) if not m.startswith('_')])
print('\nAttempting to show source (first 200 lines)')
try:
    src = inspect.getsource(DynamicFetcher)
    lines = src.splitlines()
    print('\n'.join(lines[:200]))
except Exception:
    traceback.print_exc()
