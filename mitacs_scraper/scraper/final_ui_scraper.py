import csv
import math
import os
import re
import time
from pathlib import Path
from typing import Dict, List

from playwright.sync_api import Browser, Page, sync_playwright

SITE_URL = 'https://globalink.mitacs.ca/#/student/application/projects'
OUTPUT_DIR = Path(__file__).resolve().parents[1] / 'data'

BLOCKED_RESOURCE_TYPES = {'image', 'media', 'font'}
LAUNCH_ARGS = [
    '--disable-extensions',
    '--disable-background-networking',
    '--disable-sync',
    '--disable-default-apps',
    '--no-first-run',
    '--mute-audio',
]


def normalize_spaces(value: str) -> str:
    if value is None:
        return ''
    return ' '.join(value.strip().split())


def launch_browser(playwright) -> Browser:
    return playwright.chromium.launch(
        headless=True,
        args=LAUNCH_ARGS + [f"--x-mitacs-owner={os.getpid()}"],
    )


def new_page(browser: Browser) -> Page:
    context = browser.new_context(viewport={'width': 1600, 'height': 2000})
    context.route(
        '**/*',
        lambda route: route.abort()
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES
        else route.continue_(),
    )
    page = context.new_page()
    page._mitacs_context = context
    return page


def close_page(page: Page) -> None:
    context = getattr(page, '_mitacs_context', None)
    if context is not None:
        try:
            context.close()
        except Exception:
            pass


def wait_for_condition(page: Page, predicate, timeout_s: float, poll_ms: int = 150) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        page.wait_for_timeout(poll_ms)
    return False


def wait_for_app_ready(page: Page, timeout_s: float = 30.0) -> None:
    wait_for_condition(page, lambda: page.locator('input').count() > 0, timeout_s)


def locate_keyword_input_strict(page):
    labels = page.locator('label, .input-label, .header-container')
    for i in range(labels.count()):
        text = labels.nth(i).inner_text().strip().lower()
        if 'keyword' in text:
            locator = labels.nth(i).locator('xpath=ancestor::div[1]//input | following::input[1] | parent::div//input')
            if locator.count() > 0:
                return locator.first
    for candidate in page.locator('input').all():
        try:
            if 'keyword' in (candidate.get_attribute('placeholder') or '').lower():
                return candidate
        except Exception:
            pass
    return None


def wait_for_keyword_input(page: Page, timeout_s: float = 30.0):
    wait_for_condition(page, lambda: locate_keyword_input_strict(page) is not None, timeout_s)
    return locate_keyword_input(page)


def type_into_field(field, value: str, delay: int = 25) -> None:
    field.click()
    field.fill('')
    press_sequentially = getattr(field, 'press_sequentially', None)
    if press_sequentially is not None:
        press_sequentially(value, delay=delay)
    else:
        field.type(value, delay=delay)
    field.press('Tab')


def keyword_retained(keyword_input, keyword: str) -> bool:
    if keyword_input is None:
        return True
    try:
        current = (keyword_input.input_value() or '').strip().lower()
    except Exception:
        return True
    return current == keyword.strip().lower()


def click_search_button(page) -> None:
    search_button = page.locator('button').filter(has_text='Search and Filter').first
    if search_button.count() > 0:
        search_button.click()
    else:
        page.locator('button').filter(has_text='Search').first.click()


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
            type_fn = getattr(field, 'press_sequentially', None)
            if type_fn is not None:
                type_fn(str(value), delay=15)
            else:
                field.type(str(value), delay=15)
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
        keyword_input.fill('biomedical')
        keyword_input.press('Tab')
    button = page.locator('button').filter(has_text='Search and Filter').first
    if button.count() > 0:
        button.click()
        return
    page.locator('button').filter(has_text='Search').first.click()


def total_from_text(text: str) -> int:
    m = re.search(r'Total number of projects\s*:\s*(\d+)', text or '', re.I)
    return int(m.group(1)) if m else 0


def detect_total_projects(page) -> int:
    return total_from_text(get_visible_page_text(page))


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


def block_ids(text: str) -> tuple:
    return tuple(rec['id'] for rec in parse_project_blocks_from_text(text))


def extract_projects_from_dom(page: Page) -> List[Dict[str, str]]:
    try:
        cards_data = page.evaluate('''() => {
            const dv = document.querySelector('p-dataview') || document.querySelector('.p-dataview');
            if (!dv) return null;
            const elements = Array.from(dv.querySelectorAll('.p-dataview-content > .col-12, .p-dataview-content > div.ng-star-inserted'));
            if (!elements || elements.length === 0) return null;
            
            return elements.map(el => {
                const text = el.innerText || '';
                const idMatch = text.match(/Project ID\\s*(\\d+)/i);
                const pid = idMatch ? idMatch[1].trim() : '';
                
                const pTags = Array.from(el.querySelectorAll('p')).map(p => p.innerText.trim()).filter(Boolean);
                let title = '';
                let desc = '';
                if (pTags.length > 1) {
                    title = pTags[1];
                }
                if (pTags.length > 2) {
                    desc = pTags.slice(2).join('\\n');
                }
                
                const startMatch = text.match(/Preferred start date\\s*:\\s*(\\d{4}-\\d{2}-\\d{2})/i);
                const langMatch = text.match(/Language\\s*:\\s*([A-Za-z]+)/i);
                
                return {
                    id: pid,
                    title: title,
                    description: desc,
                    start_date: startMatch ? startMatch[1] : '',
                    language: langMatch ? langMatch[1] : ''
                };
            }).filter(item => item.id !== '');
        }''')
        if cards_data:
            cleaned = []
            seen = set()
            for row in cards_data:
                pid = row['id']
                if pid in seen:
                    continue
                seen.add(pid)
                cleaned.append({
                    'id': pid,
                    'title': normalize_spaces(row.get('title', '')),
                    'description': normalize_spaces(row.get('description', '')),
                    'start_date': row.get('start_date', ''),
                    'language': row.get('language', ''),
                })
            if cleaned:
                return cleaned
    except Exception:
        pass
    return parse_project_blocks_from_text(get_visible_page_text(page))


def get_paginator_highlight(page: Page) -> str:
    try:
        return page.evaluate('''() => {
            const h = document.querySelector('.p-paginator .p-highlight, .p-paginator-page.p-highlight');
            return h ? (h.innerText || h.getAttribute('aria-label') || '').trim() : '';
        }''') or ''
    except Exception:
        return ''


def wait_for_page_stable(page: Page, old_ids: tuple, expected: int = 0, timeout_s: float = 20.0) -> str:
    deadline = time.time() + timeout_s
    old_set = set(old_ids) if old_ids else set()
    last_ids: tuple | None = None
    stable_polls = 0
    while True:
        cards = extract_projects_from_dom(page)
        ids = tuple(c['id'] for c in cards)
        if ids and not (old_set & set(ids)):
            if expected and len(ids) >= expected:
                return get_visible_page_text(page)
            if ids == last_ids:
                stable_polls += 1
                if stable_polls >= 10:
                    return get_visible_page_text(page)
            else:
                last_ids = ids
                stable_polls = 0
        if time.time() >= deadline:
            return get_visible_page_text(page)
        page.wait_for_timeout(150)


def wait_for_filtered_results(
    page: Page,
    keyword_input,
    keyword: str,
    baseline_text: str,
    default_total: int,
    previous: str | None = None,
    timeout_s: float = 15.0,
) -> str:
    def filtered() -> bool:
        text = get_visible_page_text(page)
        if 'Project ID' not in text:
            return False
        if previous is not None and text == previous:
            return False
        if not keyword_retained(keyword_input, keyword):
            return False
        new_total = total_from_text(text)
        if default_total > 0 and new_total > 0:
            return new_total != default_total
        if baseline_text:
            return text != baseline_text
        return True

    wait_for_condition(page, filtered, timeout_s, poll_ms=150)
    return get_visible_page_text(page)


def goto_keyword_page(page, keyword: str, filters: Dict[str, str] | None = None) -> str:
    page.goto(SITE_URL, wait_until='domcontentloaded', timeout=60000)
    keyword_input = wait_for_keyword_input(page)

    wait_for_condition(
        page,
        lambda: 'Project ID' in get_visible_page_text(page),
        timeout_s=8.0,
        poll_ms=200,
    )
    baseline = get_visible_page_text(page)
    default_total = total_from_text(baseline)

    if keyword_input is not None:
        try:
            type_into_field(keyword_input, keyword)
        except Exception:
            try:
                keyword_input.fill(keyword)
                keyword_input.press('Tab')
            except Exception:
                pass
    apply_optional_filters(page, filters)
    try:
        default_total = total_from_text(get_visible_page_text(page)) or default_total
    except Exception:
        pass

    click_search_button(page)
    text = wait_for_filtered_results(page, keyword_input, keyword, baseline, default_total)
    text = wait_for_page_stable(page, block_ids(baseline), expected=10, timeout_s=15.0)

    if not keyword_retained(keyword_input, keyword):
        try:
            type_into_field(keyword_input, keyword, delay=60)
            apply_optional_filters(page, filters)
            click_search_button(page)
            text = wait_for_filtered_results(
                page, keyword_input, keyword, baseline, default_total, previous=text
            )
            text = wait_for_page_stable(page, block_ids(text), expected=10, timeout_s=15.0)
        except Exception:
            pass

    return text


def click_next_page(page) -> bool:
    next_button = page.locator('.p-paginator-next').first
    if next_button.count() == 0:
        return False
    try:
        if not next_button.is_visible() or not next_button.is_enabled():
            return False
    except Exception:
        return False
    try:
        next_button.click()
    except Exception:
        return False
    return True


def count_keyword(keyword: str, filters: Dict[str, str] | None = None) -> Dict[str, int]:
    info: Dict[str, int] = {
        'keyword': keyword,
        'total_projects': 0,
        'per_page': 0,
        'total_pages': 0,
    }
    with sync_playwright() as p:
        browser = launch_browser(p)
        page = new_page(browser)
        try:
            goto_keyword_page(page, keyword, filters=filters)
            total = detect_total_projects(page)
            cards = extract_projects_from_dom(page)
            per_page = len(cards) if cards else 10

            if per_page <= 0:
                per_page = 10

            total_pages = 0
            if total > 0:
                total_pages = math.ceil(total / per_page)
            else:
                try:
                    page_buttons = page.locator('.p-paginator .p-paginator-page').all()
                    numbers = []
                    for b in page_buttons:
                        raw = (b.inner_text() or '').strip()
                        if raw.isdigit():
                            numbers.append(int(raw))
                    if numbers:
                        total_pages = max(numbers)
                except Exception:
                    total_pages = 0
                if total_pages <= 0:
                    total_pages = 1 if len(cards) > 0 else 0

            info.update({
                'total_projects': total if total > 0 else len(cards),
                'per_page': per_page,
                'total_pages': total_pages,
            })
        finally:
            close_page(page)
            browser.close()
    return info


def scrape_keyword(keyword: str, max_pages: int = 2, output_path: str = None, filters: Dict[str, str] | None = None) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    seen_ids: set = set()

    with sync_playwright() as p:
        browser = launch_browser(p)
        page = new_page(browser)
        try:
            goto_keyword_page(page, keyword, filters=filters)
            total_projects = detect_total_projects(page)
            per_page = 10

            if total_projects > 0:
                total_pages = math.ceil(total_projects / per_page)
            else:
                total_pages = 0
                try:
                    page_buttons = page.locator('.p-paginator .p-paginator-page').all()
                    numbers = []
                    for b in page_buttons:
                        raw = (b.inner_text() or '').strip()
                        if raw.isdigit():
                            numbers.append(int(raw))
                    if numbers:
                        total_pages = max(numbers)
                except Exception:
                    pass
                if total_pages <= 0:
                    total_pages = 1

            if max_pages and max_pages > 0:
                target_pages = min(max_pages, total_pages) if total_pages > 0 else max_pages
            else:
                target_pages = total_pages if total_pages > 0 else 999999

            for page_num in range(1, target_pages + 1):
                expected_this_page = min(per_page, total_projects - len(records)) if total_projects > 0 else per_page

                deadline = time.time() + 20.0
                page_cards: List[Dict[str, str]] = []
                last_count = -1
                stable_cycles = 0
                while time.time() < deadline:
                    extracted = extract_projects_from_dom(page)
                    new_cards = [c for c in extracted if c['id'] not in seen_ids]

                    if expected_this_page > 0 and len(new_cards) >= expected_this_page:
                        page_cards = new_cards
                        break

                    if len(new_cards) > 0:
                        if len(new_cards) == last_count:
                            stable_cycles += 1
                            if stable_cycles >= 10:  # 1.5 seconds stable
                                page_cards = new_cards
                                break
                        else:
                            last_count = len(new_cards)
                            stable_cycles = 0
                    page.wait_for_timeout(150)

                if not page_cards:
                    extracted = extract_projects_from_dom(page)
                    page_cards = [c for c in extracted if c['id'] not in seen_ids]

                for card in page_cards:
                    if card['id'] not in seen_ids:
                        seen_ids.add(card['id'])
                        records.append(card)

                if total_projects > 0 and len(records) >= total_projects:
                    break

                if page_num >= target_pages:
                    break

                clicked = click_next_page(page)
                if not clicked:
                    break

                target_page_str = str(page_num + 1)
                nav_deadline = time.time() + 10.0
                while time.time() < nav_deadline:
                    highlight = get_paginator_highlight(page)
                    if highlight == target_page_str:
                        break
                    current_dom = extract_projects_from_dom(page)
                    if any(c['id'] not in seen_ids for c in current_dom):
                        break
                    page.wait_for_timeout(100)

        finally:
            close_page(page)
            browser.close()

    if output_path is None:
        pages_tag = f"{len(records)}records" if max_pages == 0 else f"{min(max_pages, total_pages or max_pages)}pages"
        output_path = str((OUTPUT_DIR / f'mitacs_projects_{keyword.lower()}_{pages_tag}.csv').resolve())
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
