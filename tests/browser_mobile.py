#!/usr/bin/env python3
"""Responsive browser regression on an unchanged /sandbox/ file upload.

Requires development-only Playwright and Chromium. All financial records and
sessions live in a temporary directory; the user's database is never opened.
Optionally set VELA_SCREENSHOT_DIR to retain representative screenshots.
"""
import datetime as dt
import argparse
import os
from pathlib import Path
import secrets
import shutil

from playwright.sync_api import expect, sync_playwright
from deployment import uploaded_server

CHROME = os.environ.get('CHROMIUM_BIN') or shutil.which('chromium')
PAGES = ('dashboard', 'accounts', 'transactions', 'transfers', 'budgets',
         'debts', 'reports', 'categories', 'recurring', 'settings')
SIZES = ((320, 568), (375, 812), (430, 932), (768, 1024), (844, 390), (1440, 1000))
arguments = argparse.ArgumentParser(description=__doc__)
arguments.add_argument('--interactions-only', action='store_true',
                       help='Diagnose phone interactions without repeating the layout matrix; default runs both.')
OPTIONS = arguments.parse_args()
SCREENSHOTS = Path(os.environ['VELA_SCREENSHOT_DIR']) if os.environ.get('VELA_SCREENSHOT_DIR') else None


def settle(page):
    expect(page.locator('#main-content h1')).to_be_visible()
    expect(page.locator('.report-loading')).to_have_count(0, timeout=7000)
    # Wait for responsive chart sizing and CSS sheet/navigation transitions.
    page.wait_for_timeout(250)


def navigate(page, route):
    if page.locator('#mobile-nav').is_visible():
        direct = page.locator(f'#mobile-nav [data-page="{route}"]')
        if direct.count() and direct.is_visible():
            direct.click()
        else:
            page.locator('#mobile-more').click()
            page.locator(f'#modal-root [data-page="{route}"]').click()
    else:
        page.locator(f'#sidebar [data-page="{route}"]').click()
    expect(page.locator('#modal-root')).to_be_empty()
    settle(page)


def layout_problems(page):
    return page.evaluate("""() => {
        const viewport = document.documentElement.clientWidth;
        const problems = [];
        if (document.documentElement.scrollWidth > viewport + 1)
            problems.push(`page is ${document.documentElement.scrollWidth}px wide in ${viewport}px viewport`);
        for (const element of document.querySelectorAll('#main-content > *, #modal-root .modal, #mobile-nav')) {
            const rect = element.getBoundingClientRect();
            if (!rect.width || !rect.height) continue;
            if (rect.left < -1 || rect.right > viewport + 1)
                problems.push(`${element.className || element.id} extends outside viewport: ${rect.left}..${rect.right}`);
        }
        for (const element of document.querySelectorAll('.stat-value, .account-balance, .donut-center strong, .forecast-item > strong, .report-obligation > strong')) {
            if (element.getClientRects().length && element.clientWidth && element.scrollWidth > element.clientWidth + 1)
                problems.push(`financial value is clipped: ${element.textContent}`);
        }
        return problems;
    }""")


def check_layout(page, label):
    problems = layout_problems(page)
    if problems and SCREENSHOTS:
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOTS / ('failure-' + label + '.png')), full_page=True)
    assert not problems, label + ': ' + '; '.join(problems)


def assert_touch_target(locator, label):
    rect = locator.bounding_box()
    assert rect and rect['width'] >= 43.5 and rect['height'] >= 43.5, (label, rect)


def check_form(page, resource):
    form = page.locator(f'form[data-resource="{resource}"]')
    expect(form).to_be_visible()
    check_layout(page, 'form-' + resource)
    for field in form.locator('input:not([type=hidden]), select, textarea').all():
        if not field.is_visible():
            continue
        dimensions = field.evaluate("""element => {
            const rect = element.getBoundingClientRect();
            return {left:rect.left, right:rect.right, height:rect.height,
                    font:parseFloat(getComputedStyle(element).fontSize)};
        }""")
        assert dimensions['left'] >= -1 and dimensions['right'] <= page.viewport_size['width'] + 1, (resource, dimensions)
        assert dimensions['font'] >= 16, ('Input font can trigger iPhone zoom', resource, dimensions)
        assert dimensions['height'] >= 43.5, ('Form field is too small to tap', resource, dimensions)
    submit = form.locator('button[type=submit]')
    submit.scroll_into_view_if_needed()
    assert_touch_target(submit, resource + ' submit')
    rect = submit.bounding_box()
    assert rect['y'] >= 0 and rect['y'] + rect['height'] <= page.viewport_size['height'] + 1, ('Submit is inaccessible', resource, rect)
    obstruction = submit.evaluate("""element => {
        const r = element.getBoundingClientRect();
        const hit = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
        return element.contains(hit) ? null : {tag:hit?.tagName, cls:hit?.className,
            text:hit?.textContent?.slice(0, 100), rect:{x:r.x,y:r.y,width:r.width,height:r.height}};
    }""")
    if obstruction and SCREENSHOTS:
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOTS / ('obscured-submit-' + resource + '.png')))
    assert not obstruction, ('Another layer obscures the form submit button', resource, obstruction)
    assert_touch_target(page.locator('.modal-header [data-action=close-modal]'), 'Modal close')
    return form


def api_data(page, url, action='bootstrap'):
    response = page.request.get(url + '?action=' + action)
    assert response.ok, (response.status, response.text())
    result = response.json()
    assert result['ok'], result
    return result['data']


with uploaded_server('sandbox') as (origin, entry, public, directory):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 375, 'height': 812}, is_mobile=True,
                                      has_touch=True, timezone_id='Asia/Samarkand')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(origin + entry, wait_until='networkidle')
        api = origin + public + 'api.php'
        check_layout(page, 'mobile-onboarding')
        setup = page.locator('form[data-form=setup]')
        password = secrets.token_urlsafe(24)
        setup.locator('[name=name]').fill('Responsive Test Owner')
        setup.locator('[name=email]').fill('mobile-owner@example.test')
        setup.locator('[name=password]').fill(password)
        setup.locator('[type=submit]').click()
        settle(page)
        assert page.locator('body').evaluate('e=>parseFloat(getComputedStyle(e).fontSize)') >= 16
        csrf = api_data(page, api, 'session')['csrf']

        def create(resource, values):
            response = page.request.post(api + '?action=' + resource, data=values, headers={'X-CSRF-Token': csrf})
            payload = response.json()
            assert payload['ok'], payload
            return payload['data']

        # Realistic long labels and large UZS amounts catch layouts that appear
        # responsive only when all account names and balances are short.
        account = create('accounts', {
            'name': 'Biznesning asosiy hisob raqami — Расчётный счёт',
            'type': 'bank', 'currency': 'UZS', 'initial_balance': '1234567890.12',
            'details': 'Uzbekistan business operations / Международные платежи и ежедневные расходы',
        })
        today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5))).date().isoformat()
        create('transactions', {
            'type': 'expense', 'account_id': account['id'], 'currency': 'UZS', 'amount': '12345678.90',
            'date': today, 'description': 'Uzun izohli xarajat — Оплата оборудования для нового офиса и рабочих мест',
            'tags': ['operational', 'business', 'important'],
        })
        create('users', {'name': 'Responsive Assistant', 'email': 'mobile-assistant@example.test',
                         'password': password, 'active': True})
        page.reload(wait_until='networkidle')
        settle(page)
        page.locator('[data-currency]').first.select_option('UZS')
        expect(page.locator('#main-content')).to_have_attribute('aria-busy', 'false')
        settle(page)

        checked = 0
        for width, height in (() if OPTIONS.interactions_only else SIZES):
            page.set_viewport_size({'width': width, 'height': height})
            for locale in ('en', 'uz', 'ru'):
                page.locator('#language-select').select_option(locale)
                expect(page.locator('html')).to_have_attribute('lang', locale)
                page.wait_for_timeout(100)
                for route in PAGES:
                    navigate(page, route)
                    check_layout(page, f'{width}x{height}-{locale}-{route}')
                    text = page.locator('#main-content').inner_text()
                    assert 'undefined' not in text and 'NaN' not in text, (width, locale, route)
                    checked += 1
                    if SCREENSHOTS and locale == 'uz' and width in (375, 768, 1440) and route in ('dashboard', 'transactions', 'reports'):
                        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(SCREENSHOTS / f'{route}-{width}.png'), full_page=True)
            print(f'PASS: all owner pages in EN/UZ/RU at {width}×{height}')

        page.set_viewport_size({'width': 320, 'height': 568})
        page.locator('#language-select').select_option('en')
        expect(page.locator('html')).to_have_attribute('lang', 'en')
        page.wait_for_timeout(150)
        navigate(page, 'transactions')
        for item in page.locator('#mobile-nav button:visible').all():
            assert_touch_target(item, 'Bottom navigation')
        assert_touch_target(page.locator('#quick-add'), 'Quick add')
        page.locator('#mobile-more').click()
        expect(page.locator('.more-menu')).to_be_visible()
        for item in page.locator('.more-menu button').all():
            assert_touch_target(item, 'More navigation')
        page.keyboard.press('Escape')
        expect(page.locator('#modal-root')).to_be_empty()
        expect(page.locator('#mobile-more')).to_be_focused()

        # The drawer must trap focus and block the page beneath it, then restore
        # normal navigation when closed or when crossing to the desktop layout.
        sidebar = page.locator('#sidebar')
        assert sidebar.evaluate('element => element.inert')
        page.locator('#sidebar-toggle').click()
        expect(page.locator('#sidebar-toggle')).to_have_attribute('aria-expanded', 'true')
        expect(sidebar).to_have_attribute('role', 'dialog')
        expect(page.locator('#sidebar-close')).to_be_focused()
        assert page.locator('.app-main').evaluate('element => element.inert')
        assert page.locator('#mobile-nav').evaluate('element => element.inert')
        page.locator('#logout-button').focus()
        page.keyboard.press('Tab')
        expect(sidebar.locator('.brand')).to_be_focused()
        page.keyboard.press('Shift+Tab')
        expect(page.locator('#logout-button')).to_be_focused()
        page.locator('#sidebar-backdrop').click(position={'x': 316, 'y': 100})
        expect(page.locator('#sidebar-toggle')).to_have_attribute('aria-expanded', 'false')
        expect(page.locator('#sidebar-toggle')).to_be_focused()
        assert not page.locator('.app-main').evaluate('element => element.inert')
        page.locator('#sidebar-toggle').click()
        page.set_viewport_size({'width': 1440, 'height': 1000})
        page.wait_for_timeout(300)
        assert not page.locator('body').evaluate('element => element.classList.contains("sidebar-open")')
        assert not sidebar.evaluate('element => element.inert')
        assert not page.locator('.app-main').evaluate('element => element.inert')
        assert not page.locator('#sidebar-backdrop').is_visible()
        page.locator('#sidebar [data-page=accounts]').click()
        settle(page)
        page.set_viewport_size({'width': 320, 'height': 568})
        page.wait_for_timeout(300)
        assert sidebar.evaluate('element => element.inert')

        # Preferences stay usable inside More, including after re-rendering the
        # sheet in another language or theme.
        page.locator('#mobile-more').click()
        page.locator('.more-preferences [data-locale]').select_option('ru')
        expect(page.locator('html')).to_have_attribute('lang', 'ru')
        expect(page.locator('.more-preferences [data-locale]')).to_have_value('ru')
        previous_theme = page.locator('html').get_attribute('data-theme')
        page.locator('.more-preferences [data-action=toggle-theme]').click()
        expect(page.locator('html')).to_have_attribute('data-theme', 'light' if previous_theme == 'dark' else 'dark')
        expect(page.locator('.more-menu')).to_be_visible()
        check_layout(page, 'more-preferences')
        page.locator('.more-preferences [data-locale]').select_option('en')
        expect(page.locator('html')).to_have_attribute('lang', 'en')
        page.keyboard.press('Escape')
        expect(page.locator('#modal-root')).to_be_empty()
        print('PASS: drawer focus trap/backdrop/desktop resize and live More language/theme preferences')

        navigate(page, 'reports')
        page.locator('[data-action=report-period][data-period=custom]').click()
        for control in page.locator('.report-date-row input, .report-date-row button').all():
            expect(control).to_be_visible()
            assert_touch_target(control, 'Custom report date/filter')
        check_layout(page, 'mobile-custom-report-dates')
        page.locator('#report-charts .chart-data-details summary').click()
        expect(page.locator('#report-charts .chart-data-details[open] table')).to_be_visible()
        check_layout(page, 'mobile-expanded-chart-data')
        for target in ('report-insights', 'report-accounts', 'report-planning'):
            page.locator(f'[data-action=report-section][data-target="{target}"]').click()
            expect(page.locator('#' + target)).to_be_focused()
            page.wait_for_function("""id => {
                const r = document.getElementById(id).getBoundingClientRect();
                return r.top >= 0 && r.top < innerHeight - 80;
            }""", arg=target)
        print('PASS: mobile custom date filters, expanded report data and section shortcuts')

        # Every financial form fits a narrow phone and offers a reachable submit
        # action; settings also covers the long assistant credential form.
        for route, action, resource in (
            ('accounts', 'new-account', 'accounts'),
            ('transactions', 'new-transaction', 'transactions'),
            ('transfers', 'new-transfer', 'transfers'),
            ('budgets', 'new-budget', 'budgets'),
            ('debts', 'new-debt', 'debts'),
            ('categories', 'new-category', 'categories'),
            ('categories', 'new-tag', 'tags'),
            ('recurring', 'new-recurring', 'recurring'),
            ('settings', 'new-user', 'users'),
        ):
            navigate(page, route)
            page.locator(f'#main-content [data-action="{action}"]').first.click()
            check_form(page, resource)
            page.locator('.modal-header [data-action=close-modal]').click()
            expect(page.locator('#modal-root')).to_be_empty()
        print('PASS: mobile touch targets, More/Escape/focus return, and all nine financial/team forms')

        # Enter and edit actual financial data on the narrowest phone. Shrink the
        # viewport while a field is focused to exercise a keyboard-sized space.
        navigate(page, 'transactions')
        page.locator('#quick-add').click()
        form = page.locator('form[data-resource=transactions]')
        form.locator('[name=account_id]').select_option(str(account['id']))
        form.locator('[name=amount]').fill('45.67')
        form.locator('[name=description]').fill('Narrow phone transaction')
        form.locator('[name=description]').focus()
        page.set_viewport_size({'width': 320, 'height': 360})
        check_form(page, 'transactions')
        form.locator('[type=submit]').click()
        expect(page.locator('#modal-root')).to_be_empty(timeout=7000)
        transaction = next(item for item in api_data(page, api)['transactions'] if item['description'] == 'Narrow phone transaction')
        page.set_viewport_size({'width': 320, 'height': 568})
        page.locator(f'[data-action=edit][data-resource=transactions][data-id="{transaction["id"]}"]').click()
        form = page.locator('form[data-resource=transactions]')
        form.locator('[name=amount]').fill('50.25')
        check_form(page, 'transactions')
        form.locator('[type=submit]').click()
        expect(page.locator('#modal-root')).to_be_empty(timeout=7000)
        updated = next(item for item in api_data(page, api)['transactions'] if item['id'] == transaction['id'])
        assert updated['amount'] == 50.25
        print('PASS: transaction create/edit in 320px phone and 320×360 focused-field viewport')

        # The assistant has fewer modules, so its bottom navigation must still
        # fit and expose every allowed page without private owner controls.
        page.request.post(api + '?action=logout', data={}, headers={'X-CSRF-Token': csrf})
        page.reload(wait_until='networkidle')
        login = page.locator('form[data-form=login]')
        login.locator('[name=email]').fill('mobile-assistant@example.test')
        login.locator('[name=password]').fill(password)
        login.locator('[type=submit]').click()
        settle(page)
        for locale in ('uz', 'ru'):
            page.locator('#language-select').select_option(locale)
            expect(page.locator('html')).to_have_attribute('lang', locale)
            page.wait_for_timeout(100)
            for route in ('transactions', 'categories', 'recurring', 'settings'):
                navigate(page, route)
                check_layout(page, 'assistant-' + locale + '-' + route)
        assert not page.locator('#mobile-nav [data-page=accounts]').is_visible()
        assert not page.locator('#main-content [data-action=reset-finances]').count()
        assert not errors, errors
        print(f'All mobile checks passed: {checked} owner layouts, assistant views, touch controls and real mutations.')
        browser.close()
