import time

from mitacs_scraper.scraper.final_ui_scraper import scrape_keyword

t0 = time.time()
rows = scrape_keyword("genetics", max_pages=8)
print(f"records: {len(rows)} ({time.time() - t0:.1f}s)")
print(f"first: {rows[0]['id']} | {rows[0]['title'][:60]}")
print(f"last:  {rows[-1]['id']} | {rows[-1]['title'][:60]}")

t1 = time.time()
rows_all = scrape_keyword("genetics", max_pages=0)
print(f"all-pages mode records: {len(rows_all)} ({time.time() - t1:.1f}s)")
print(f"all-pages last: {rows_all[-1]['id']} | {rows_all[-1]['title'][:60]}")
