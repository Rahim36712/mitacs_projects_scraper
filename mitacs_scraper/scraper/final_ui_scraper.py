import csv
import math
import re
from pathlib import Path
from typing import Dict, List

from playwright.sync_api import sync_playwright

SITE_URL = 'https://globalink.mitacs.ca/#/student/application/projects'
OUTPUT_DIR = Path(__file__).resolve().parents[1] / 'data'


def normalize_spaces(value: str) -> str:
    if value is None:
        return ''
    return ' '.join(value.strip().split())


def locate_keyword_input(page):
    labels = page.locator('label, .input-label, .header-container')
    for i in range(labels.count()):
        text = labels.nth(i).inner_text().strip().lower()
        if 'keyword search' in text or 'keyword' in text:
            locator = labels.nth(i).locator('xpath=ancestor::div[1]//input | following::input[1] | parent::div//input')
            if locator.count() > 0:
                return locator.first
    for candidate in page.locator('input').all():
        try:
            if 'keyword' in (candidate.get_attribute('placeholder') or '').lower():
                return candidate
        except Exception:
            pass
    inputs = page.locator('input')
    if inputs.count() > 0:
        return inputs.first
    return None


def locate_field_by_name(page, *names: str):
    normalized = tuple(name.lower() for name in names if name)
    if not normalized:
        return None
    for label in page.locator('label, .input-label, .field-label, .header-container, span, div').all():
        try:
            text = (label.inner_text() or '').lower()
        except Exception:
            continue
        if any(name in text for name in normalized):
            candidate = label.locator('xpath=ancestor::div[1]//input | following::input[1] | parent::div//input | ancestor::div[1]//select | following::select[1] | parent::div//select')
            if candidate.count() > 0:
                return candidate.first
    for candidate in page.locator('input, select, textarea').all():
        try:
            attrs = [candidate.get_attribute('placeholder') or '', candidate.get_attribute('aria-label') or '', candidate.get_attribute('name') or '', candidate.get_attribute('id') or '']
            label_text = ' '.join(attrs).lower()
        except Exception:
            continue
        if any(name in label_text for name in normalized):
            return candidate
    return None


def apply_optional_filters(page, filters: Dict[str, str] | None):
    if not filters:
        return
    for key, value in filters.items():
        if not value:
            continue
        field_aliases = {
            'language': ('language',),
            'faculty_province': ('faculty province', 'province'),
            'faculty_university': ('faculty university', 'university'),
            'faculty_campus': ('faculty campus', 'campus'),
            'faculty_first_name': ('faculty first name', 'first name'),
            'faculty_last_name': ('faculty last name', 'last name'),
            'academic_achievement': ('academic achievement', 'achievement'),
        }
        field = locate_field_by_name(page, *field_aliases.get(key, (key,)))
        if field is None:
            continue
        try:
            field.click()
            field.fill('')
            field.type(str(value), delay=20)
            field.press('Tab')
        except Exception:
            try:
                field.select_option(label=str(value))
            except Exception:
                pass


def click_search_and_filter(page):
    keyword_input = locate_keyword_input(page)
    if keyword_input is not None:
        keyword_input.click()
        keyword_input.fill('')
        keyword_input.type('biomedical', delay=40)
        keyword_input.press('Tab')
    button = page.locator('button').filter(has_text='Search and Filter').first
    if button.count() > 0:
        button.click()
        return
    page.locator('button').filter(has_text='Search').first.click()


def detect_total_projects(page) -> int:
    text = page.locator('body').inner_text()
    m = re.search(r'Total number of projects\s*:\s*(\d+)', text, re.I)
    if m:
        return int(m.group(1))
    return 0


def get_visible_page_text(page) -> str:
    return page.locator('body').inner_text()


def parse_project_blocks_from_text(raw_text: str) -> List[Dict[str, str]]:
    text = raw_text.replace('\xa0', ' ')
    # Split on project id boundaries.
    segments = re.split(r'(?=Project ID\s*\d+)', text)
    records: List[Dict[str, str]] = []

    for seg in segments:
        seg = seg.strip()
        if not seg or 'Project ID' not in seg:
            continue
        m_id = re.search(r'Project ID\s*(\d+)', seg, re.I)
        if not m_id:
            continue
        pid = m_id.group(1)
        lines = [ln.strip() for ln in seg.splitlines() if ln.strip()]
        if not lines:
            continue
        title = ''
        desc_lines: List[str] = []
        seen_title = False
        for ln in lines[1:]:
            if re.match(r'^(Faculty supervisor|Faculty Province|Faculty University|Faculty Campus|Project Location|Language|Preferred start date|View Detail|Project ID)', ln, re.I):
                if not seen_title:
                    break
                break
            if not seen_title:
                title = ln
                seen_title = True
                continue
            desc_lines.append(ln)
        if not title and len(lines) > 1:
            title = lines[1]
        # If no explicit title/description split, take everything between title and metadata labels.
        if not desc_lines:
            # re-scan from the title line onward and stop at metadata labels
            for idx, ln in enumerate(lines[1:], start=1):
                if re.match(r'^(Faculty supervisor|Faculty Province|Faculty University|Faculty Campus|Project Location|Language|Preferred start date|View Detail)', ln, re.I):
                    break
                if idx > 1:
                    desc_lines.append(ln)

        description = '\n'.join(desc_lines).strip()
        if not description:
            description = title

        m_start = re.search(r'Preferred start date\s*:\s*(\d{4}-\d{2}-\d{2})', seg, re.I)
        start_date = m_start.group(1) if m_start else ''
        m_lang = re.search(r'Language\s*:\s*([A-Za-z]+)', seg, re.I)
        language = m_lang.group(1).strip() if m_lang else ''

        records.append({
            'id': pid,
            'title': normalize_spaces(title),
            'description': normalize_spaces(description).replace('\n', '\n'),
            'start_date': start_date,
            'language': language,
        })
    # dedupe by id, preserving first-seen order
    deduped: List[Dict[str, str]] = []
    seen = set()
    for rec in records:
        if rec['id'] in seen:
            continue
        seen.add(rec['id'])
        deduped.append(rec)
    return deduped


def goto_keyword_page(page, keyword: str, filters: Dict[str, str] | None = None):
    page.goto(SITE_URL, wait_until='networkidle', timeout=120000)
    keyword_input = locate_keyword_input(page)
    if keyword_input is not None:
        keyword_input.click()
        keyword_input.fill('')
        keyword_input.type(keyword, delay=40)
    apply_optional_filters(page, filters)
    search_button = page.locator('button').filter(has_text='Search and Filter').first
    if search_button.count() > 0:
        search_button.click()
    else:
        page.locator('button').filter(has_text='Search').first.click()
    page.wait_for_timeout(2500)
    page.wait_for_load_state('networkidle', timeout=20000)


def navigate_to_page(page, page_number: int):
    if page_number <= 1:
        return
    button = page.locator('button').filter(has_text=str(page_number)).first
    if button.count() > 0:
        try:
            if button.is_visible() and button.is_enabled():
                button.click()
                page.wait_for_timeout(1500)
                page.wait_for_load_state('networkidle', timeout=20000)
                return
        except Exception:
            pass
    next_button = page.locator('.p-paginator-next').first
    if next_button.count() == 0:
        return
    for _ in range(page_number - 1):
        try:
            if not next_button.is_visible() or not next_button.is_enabled():
                break
            next_button.click()
            page.wait_for_timeout(1200)
            page.wait_for_load_state('networkidle', timeout=20000)
            next_button = page.locator('.p-paginator-next').first
        except Exception:
            break


def count_keyword(keyword: str, filters: Dict[str, str] | None = None) -> Dict[str, int]:
    info: Dict[str, int] = {
        'keyword': keyword,
        'total_projects': 0,
        'per_page': 0,
        'total_pages': 0,
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 2000})
        try:
            goto_keyword_page(page, keyword, filters=filters)
            text = get_visible_page_text(page)
            total = detect_total_projects(page)
            per_page = len(parse_project_blocks_from_text(text))

            if per_page <= 0:
                per_page = 10

            total_pages = 0
            if total > 0:
                total_pages = math.ceil(total / per_page)
            else:
                try:
                    page_buttons = page.locator('.p-paginator-page')
                    numbers = []
                    for i in range(page_buttons.count()):
                        raw = (page_buttons.nth(i).inner_text() or '').strip()
                        if raw.isdigit():
                            numbers.append(int(raw))
                    if numbers:
                        total_pages = max(numbers)
                except Exception:
                    total_pages = 0
                if total_pages <= 0:
                    total_pages = 1

            info.update({
                'total_projects': total,
                'per_page': per_page,
                'total_pages': total_pages,
            })
        finally:
            browser.close()
    return info


def scrape_keyword(keyword: str, max_pages: int = 2, output_path: str = None, filters: Dict[str, str] | None = None) -> List[Dict[str,str]]:
    records: List[Dict[str,str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 2000})
        goto_keyword_page(page, keyword, filters=filters)
        if max_pages and max_pages > 0:
            page_limit = max_pages
            for page_num in range(1, page_limit + 1):
                if page_num > 1:
                    navigate_to_page(page, page_num)
                text = get_visible_page_text(page)
                page_records = parse_project_blocks_from_text(text)
                for rec in page_records:
                    if rec['id'] and rec['id'] not in {r['id'] for r in records}:
                        records.append(rec)
        else:
            page_num = 1
            while True:
                text = get_visible_page_text(page)
                page_records = parse_project_blocks_from_text(text)
                for rec in page_records:
                    if rec['id'] and rec['id'] not in {r['id'] for r in records}:
                        records.append(rec)
                next_button = page.locator('.p-paginator-next').first
                if next_button.count() == 0:
                    break
                try:
                    if not next_button.is_visible() or not next_button.is_enabled():
                        break
                except Exception:
                    break
                next_button.click()
                page.wait_for_timeout(1500)
                page.wait_for_load_state('networkidle', timeout=20000)
                page_num += 1
        browser.close()

    if output_path is None:
        output_path = str((OUTPUT_DIR / f'mitacs_projects_{keyword.lower()}_{min(max_pages, len(records)) or max_pages}pages.csv').resolve())
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=['id','title','description','start_date','language'])
        writer.writeheader()
        for row in records:
            writer.writerow({
                'id': row['id'],
                'title': row['title'],
                'description': row['description'],
                'start_date': row['start_date'],
                'language': row['language'],
            })
    return records


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Scrape MITACS Globalink project list into CSV.')
    parser.add_argument('--keyword', default='biomedical', help='Keyword to search for')
    parser.add_argument('--max-pages', type=int, default=2, help='How many result pages to scrape (default 2)')
    parser.add_argument('--output', default=None, help='Optional CSV output path')
    args = parser.parse_args()

    rows = scrape_keyword(args.keyword, max_pages=args.max_pages, output_path=args.output)
    print(f'Wrote {len(rows)} records to CSV.')
