from mitacs_scraper.scraper.crawl_keyword import collect_pages_for_keyword, parse_projects_from_page, crawl_keyword_to_csv
import re
import json

keyword = 'biomedical'

print('Running verification for keyword:', keyword)
pages, captured = collect_pages_for_keyword(keyword, max_pages=1, use_typing=True, return_capture=True)
if not pages:
    print('No pages returned')
    raise SystemExit(1)
page = pages[0]
print('Captured XHRs:', json.dumps(captured, indent=2))
# detect total number shown on page
m_total = re.search(r'Total number of projects\s*:\s*(\d+)', page, re.I)
if m_total:
    total = int(m_total.group(1))
else:
    total = None

per_page = max(1, len(re.findall(r'Project ID\s*(\d+)', page)))
# try to get max page button
m_pages = re.findall(r'\b(\d+)\b', page)
max_page = None
if m_pages:
    try:
        max_page = max(int(x) for x in m_pages if int(x) < 5000)
    except Exception:
        max_page = None

print('Verification results:')
print(' total (from page):', total)
print(' items on page (per_page heuristic):', per_page)
print(' max page numeric found (heuristic):', max_page)

# show sample parsed records
recs = parse_projects_from_page(page)
print('Parsed records from page 1 (count):', len(recs))
print(json.dumps(recs[:5], indent=2, ensure_ascii=False))

# If verification looks reasonable (per_page>=5 and total>20), proceed to scrape first 2 pages
proceed = (per_page >= 5) and (total is None or total >= 20)
if proceed:
    print('\nVerification passed; scraping first 2 pages to CSV...')
    out = 'D:/AI STUFF/PROJECTS/SCRAPER/mitacs_scraper/data/mitacs_projects_biomedical_2pages.csv'
    n = crawl_keyword_to_csv(keyword, out, max_pages=2)
    print('Scraped records:', n, '->', out)
else:
    print('\nVerification failed; not scraping.')
    raise SystemExit(2)
