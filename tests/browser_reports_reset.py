#!/usr/bin/env python3
"""Real browser regression for readable reports and confirmed cleanup in /sandbox/."""
import csv
import datetime as dt
import io
import os
from pathlib import Path
import secrets
import shutil
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright, expect
from deployment import uploaded_server

CHROME = os.environ.get('CHROMIUM_BIN') or shutil.which('chromium')

def report_response(response):
    return parse_qs(urlsplit(response.url).query).get('action') == ['reports']

with uploaded_server('sandbox') as (origin, entry, public, directory):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, timezone_id='Asia/Samarkand')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(origin + entry, wait_until='networkidle')
        setup = page.locator('form[data-form=setup]')
        password = secrets.token_urlsafe(24)
        setup.locator('[name=name]').fill('Feature Owner')
        setup.locator('[name=email]').fill('features@example.test')
        setup.locator('[name=password]').fill(password)
        setup.locator('[type=submit]').click()
        expect(page.locator('#main-content h1')).to_have_text('Your money, in focus.')
        assert page.locator('body').evaluate('e=>parseFloat(getComputedStyle(e).fontSize)') >= 16
        assert page.locator('#sidebar .nav-item').first.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)') >= 15
        assert page.locator('.stat-label').first.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)') >= 14
        assert page.locator('.transaction-name').first.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)') >= 15
        session = page.request.get(origin + public + 'api.php?action=session').json()['data']
        headers = {'X-CSRF-Token': session['csrf']}
        def create(resource, values):
            result = page.request.post(origin + public + 'api.php?action=' + resource, data=values, headers=headers).json()
            assert result['ok'], result
            return result['data']
        account = create('accounts', {'name':'My real account', 'type':'cash', 'currency':'USD', 'initial_balance':250})
        category = create('categories', {'name':'Real groceries', 'type':'expense'})
        today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5))).date().isoformat()
        transaction = create('transactions', {'type':'expense', 'amount':12.34, 'currency':'USD', 'account_id':account['id'], 'category_id':category['id'], 'date':today, 'description':'My real expense'})
        page.reload(wait_until='networkidle')
        with page.expect_response(report_response) as loaded:
            page.locator('#sidebar [data-page=reports]').click()
        assert loaded.value.json()['ok']
        expect(page.locator('#report-comparison-chart')).to_be_visible()
        expect(page.locator('#report-trend-chart')).to_be_visible()
        assert page.evaluate('Object.keys(Chart.instances).length') == 2
        assert page.evaluate('Chart.defaults.font.size') >= 14
        expect(page.locator('.report-category-list')).to_contain_text('Real groceries')
        expect(page.locator('.report-account-table')).to_contain_text('My real account')
        expect(page.locator('.report-insight-list')).not_to_be_empty()
        for width in (1440, 1024, 768, 390):
            page.set_viewport_size({'width':width,'height':1000})
            page.wait_for_timeout(400)
            if not page.evaluate('document.documentElement.scrollWidth <= innerWidth'):
                print('OVERFLOW', width, page.evaluate("() => [...document.querySelectorAll('#app-shell *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1 && e.getBoundingClientRect().width>0).slice(0,25).map(e=>({tag:e.tagName,cls:e.className,right:Math.round(e.getBoundingClientRect().right),width:Math.round(e.getBoundingClientRect().width),text:e.innerText?.slice(0,80)}))"))
                page.screenshot(path='/tmp/vela-report-overflow.png',full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Report overflows at {width}px'
        page.set_viewport_size({'width':1440,'height':1000})
        for preset, expected_days in [('last_month', None), ('last90', 90), ('this_month', None)]:
            with page.expect_response(report_response) as loaded:
                page.locator(f'[data-action=report-period][data-period={preset}]').click()
            result = loaded.value.json()['data']
            if expected_days: assert result['period']['days'] == expected_days
            expect(page.locator('.report-loading')).to_have_count(0)
        with page.expect_response(report_response) as loaded:
            page.locator('[data-currency]').select_option('UZS')
        assert loaded.value.json()['data']['currency'] == 'UZS'
        with page.expect_response(report_response):
            page.locator('[data-currency]').select_option('USD')
        with page.expect_response(report_response) as loaded:
            page.locator('[data-report-account]').select_option(str(account['id']))
        result = loaded.value.json()['data']
        assert result['period']['income'] == 0 and result['period']['expense'] == 12.34
        assert result['period']['savings_rate'] is None
        page.locator('[data-report-date=from]').fill(today)
        page.locator('[data-report-date=to]').fill(today)
        with page.expect_response(report_response) as loaded:
            page.locator('form[data-form=report-filters] [type=submit]').click()
        result = loaded.value.json()['data']
        assert result['from'] == result['to'] == today
        assert result['period']['average_daily_expense'] == 12.34
        assert result['period']['days'] == 1
        with page.expect_download() as downloaded:
            page.locator('a[href*="action=report_export"]').click()
        rows = list(csv.reader(io.StringIO(Path(downloaded.value.path()).read_text(encoding='utf-8-sig'))))
        assert any('Real groceries' in row and '12.34' in row for row in rows)
        assert all('Humo card' not in row for row in rows)
        with page.expect_response(report_response):
            page.locator('[data-report-account]').select_option('')
        with page.expect_response(report_response):
            page.locator('[data-action=report-period][data-period=this_month]').click()
        page.locator('#language-select').select_option('uz')
        expect(page.locator('html')).to_have_attribute('lang','uz')
        expect(page.locator('.report-insight-list')).not_to_contain_text('report_insight_')
        for width in (1440, 390):
            page.set_viewport_size({'width':width,'height':1000})
            page.wait_for_timeout(400)
            if not page.evaluate('document.documentElement.scrollWidth <= innerWidth'):
                print('UZ_OVERFLOW', page.evaluate("() => ({scroll:document.documentElement.scrollWidth,inner:innerWidth,items:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+.2 && e.getBoundingClientRect().width>0).slice(0,15).map(e=>({cls:e.className,right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width,text:e.innerText?.slice(0,60)}))})"))
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Uzbek report overflows at {width}px'
            if output := os.environ.get('VELA_SCREENSHOT_DIR'):
                Path(output).mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(Path(output)/f'reports-{width}.png'), full_page=True)
        page.set_viewport_size({'width':1440,'height':1000})
        page.locator('#language-select').select_option('en')
        expect(page.locator('html')).to_have_attribute('lang','en')
        print('PASS: readable desktop/mobile typography, real report filters/charts/CSV/Uzbek insights')
        page.locator('#sidebar [data-page=settings]').click()
        page.locator('[data-action=clear-sample-data]').click()
        form = page.locator('form[data-form=financial-reset]')
        expect(form.locator('[type=submit]')).to_be_disabled()
        form.locator('[name=current_password]').fill('wrong password')
        form.locator('[name=confirmation]').fill('REMOVE SAMPLE DATA')
        expect(form.locator('[type=submit]')).to_be_enabled()
        form.locator('[type=submit]').click()
        expect(form.locator('.form-error')).to_be_visible()
        assert page.request.get(origin+public+'api.php?action=demo_status').json()['data']['sample_records'] > 0
        form.locator('[name=current_password]').fill(password)
        form.locator('[type=submit]').click()
        expect(page.locator('#modal-root')).to_be_empty()
        expect(page.locator('[data-action=clear-sample-data]')).to_be_disabled()
        bootstrap = page.request.get(origin+public+'api.php?action=bootstrap').json()['data']
        assert len(bootstrap['accounts']) == len(bootstrap['transactions']) == 1
        assert bootstrap['accounts'][0]['id'] == account['id']
        assert bootstrap['transactions'][0]['id'] == transaction['id']
        assert bootstrap['accounts'][0]['current_balance'] == 237.66
        print('PASS: cleanup requires password and phrase, removes samples, keeps personal records')
        page.locator('[data-action=reset-finances]').click()
        form = page.locator('form[data-form=financial-reset]')
        expect(form.locator('[type=submit]')).to_be_disabled()
        expect(form).to_contain_text('ALL financial records')
        form.locator('[name=current_password]').fill(password)
        form.locator('[name=confirmation]').fill('RESET FINANCE')
        expect(form.locator('[type=submit]')).to_be_disabled()
        form.locator('[name=confirmation]').fill('RESET FINANCES')
        form.locator('[type=submit]').click()
        expect(page.locator('#modal-root')).to_be_empty()
        expect(page.locator('[data-action=reset-finances]')).to_be_disabled()
        bootstrap = page.request.get(origin+public+'api.php?action=bootstrap').json()['data']
        for resource in ['accounts','transactions','categories','tags','debts','budgets','recurring','transfers']:
            assert bootstrap[resource] == [], resource
        assert len(bootstrap['users']) == 1 and len(bootstrap['audit']) > 0
        with page.expect_response(report_response):
            page.locator('#sidebar [data-page=reports]').click()
        expect(page.locator('.report-empty')).to_be_visible()
        page.locator('#logout-button').click()
        form = page.locator('form[data-form=login]')
        expect(form).to_be_visible()
        form.locator('[name=email]').fill('features@example.test')
        form.locator('[name=password]').fill(password)
        form.locator('[type=submit]').click()
        expect(page.locator('#main-content h1')).to_have_text('Your money, in focus.')
        print('PASS: confirmed full reset preserves owner credentials/audit and produces usable empty reports')
        assert not errors, errors
        browser.close()
        print('All report and reset browser checks passed.')
