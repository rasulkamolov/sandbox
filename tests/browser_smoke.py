#!/usr/bin/env python3
"""Optional real Chromium UI smoke tests. Requires Python playwright + Chromium.
Uses a temporary server/database; never modifies the application's financial DB.
"""
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PHP = os.environ.get('PHP_BIN', shutil.which('php') or '/workspace/.runtime/php/bin/php')
CHROME = os.environ.get('CHROMIUM_BIN', shutil.which('chromium') or '')

with tempfile.TemporaryDirectory(prefix='vela-ui-') as directory:
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    sessions = Path(directory) / 'sessions'
    sessions.mkdir()
    process = subprocess.Popen([PHP, '-S', f'127.0.0.1:{port}', '-t', str(ROOT / 'public')],
        env={**os.environ, 'FINANCE_DB_PATH': str(Path(directory) / 'finance.db'), 'FINANCE_SESSION_PATH': str(sessions)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with urlopen(base + '/api.php?action=session', timeout=1):
                    break
            except Exception:
                if process.poll() is not None:
                    raise RuntimeError('PHP server exited')
                time.sleep(0.05)
        else:
            raise RuntimeError('PHP server did not start')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**({'executable_path': CHROME} if CHROME else {}), headless=True,
                args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base, wait_until='networkidle')
            setup = page.locator('form[data-form="setup"]')
            expect(setup).to_be_visible()
            setup.locator('[name=name]').fill('Browser Test Owner')
            setup.locator('[name=email]').fill('ui-owner@example.test')
            password = secrets.token_urlsafe(24)
            setup.locator('[name=password]').fill(password)
            setup.locator('button[type=submit]').click()
            expect(page.locator('#main-content h1')).to_have_text('Your money, in focus.')
            assert page.evaluate('!!window.Chart && !!window.lucide')
            expect(page.locator('canvas')).to_have_count(2)
            assert page.locator('svg.lucide').count() > 30
            assert page.evaluate('Object.keys(Chart.instances).length') == 2
            screenshot_dir = os.environ.get('VELA_SCREENSHOT_DIR')
            if screenshot_dir:
                Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(Path(screenshot_dir) / 'dashboard-dark.png'), full_page=True)

            # Every owner module renders; dashboard/report charts execute.
            for route in ['accounts', 'transactions', 'transfers', 'budgets', 'debts', 'reports', 'categories', 'recurring', 'settings']:
                page.locator(f'#sidebar [data-page="{route}"]').click()
                expect(page.locator('#main-content h1')).to_be_visible()
                assert 'NaN' not in page.locator('#main-content').inner_text()
                assert 'undefined' not in page.locator('#main-content').inner_text()
            print('PASS: secure onboarding, charts, icons and all owner module views')

            page.locator('#sidebar [data-page=accounts]').click()
            page.locator('#main-content [data-action=new-account]').first.click()
            form = page.locator('form[data-resource=accounts]')
            form.locator('[name=name]').fill('UI cash wallet')
            form.locator('[name=type]').select_option('cash')
            form.locator('[name=initial_balance]').fill('100')
            form.locator('[name=details]').fill('Created in browser test')
            form.locator('button[type=submit]').click()
            expect(page.locator('#main-content .account-name').filter(has_text='UI cash wallet')).to_be_visible()
            data = page.request.get(base + '/api.php?action=bootstrap').json()['data']
            account = next(row for row in data['accounts'] if row['name'] == 'UI cash wallet')
            assert account['current_balance'] == 100

            # A transaction entered through the real modal changes the real balance.
            page.locator('#quick-add').click()
            form = page.locator('form[data-resource=transactions]')
            form.locator('[name=account_id]').select_option(str(account['id']))
            form.locator('[name=amount]').fill('12.34')
            form.locator('[name=description]').fill('Browser expense with receipt')
            form.locator('[name=tags]').fill('ui, verified')
            form.locator('[name=receipt]').fill('receipt-2026-001')
            form.locator('button[type=submit]').click()
            expect(page.locator('#modal-root')).to_be_empty()
            page.locator('#sidebar [data-page=transactions]').click()
            expect(page.locator('.transaction-name').filter(has_text='Browser expense with receipt')).to_be_visible()
            data = page.request.get(base + '/api.php?action=bootstrap').json()['data']
            assert next(a for a in data['accounts'] if a['id'] == account['id'])['current_balance'] == 87.66
            transaction = next(t for t in data['transactions'] if t['description'] == 'Browser expense with receipt')
            row = page.locator('tr').filter(has_text='Browser expense with receipt')
            row.locator('[data-action=edit]').click()
            form = page.locator('form[data-resource=transactions]')
            form.locator('[name=amount]').fill('20')
            form.locator('button[type=submit]').click()
            expect(page.locator('#modal-root')).to_be_empty()
            row = page.locator('tr').filter(has_text='Browser expense with receipt')
            expect(row).to_contain_text('20.00')
            row.locator('[data-action=delete]').click()
            page.locator('[data-action=confirm-delete]').click()
            expect(page.locator('.transaction-name').filter(has_text='Browser expense with receipt')).to_have_count(0)
            data = page.request.get(base + '/api.php?action=bootstrap').json()['data']
            assert next(a for a in data['accounts'] if a['id'] == account['id'])['current_balance'] == 100
            print('PASS: account creation, transaction create/edit/delete, receipt/tag persistence and balance reversal')

            page.locator('#theme-toggle').click()
            expect(page.locator('html')).to_have_attribute('data-theme', 'light')
            page.locator('#language-select').select_option('uz')
            expect(page.locator('html')).to_have_attribute('lang', 'uz')
            assert page.request.get(base + '/api.php?action=session').json()['data']['locale'] == 'uz'
            page.locator('#language-select').select_option('ru')
            expect(page.locator('html')).to_have_attribute('lang', 'ru')
            page.reload(wait_until='networkidle')
            expect(page.locator('html')).to_have_attribute('lang', 'ru')
            expect(page.locator('html')).to_have_attribute('data-theme', 'light')
            page.locator('#language-select').select_option('en')
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            print('PASS: language session persistence and theme persistence')

            # Mobile bottom navigation, card list and bottom sheet modal.
            page.set_viewport_size({'width': 390, 'height': 844})
            expect(page.locator('#mobile-nav')).to_be_visible()
            page.locator('#mobile-nav [data-page=transactions]').click()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#quick-add').click()
            expect(page.locator('[role=dialog]')).to_be_visible()
            assert page.locator('[role=dialog]').bounding_box()['width'] <= 390
            page.keyboard.press('Escape')
            expect(page.locator('#modal-root')).to_be_empty()
            page.locator('#mobile-more').click()
            expect(page.locator('.more-menu')).to_be_visible()
            page.locator('.more-menu [data-page=dashboard]').click()
            expect(page.locator('#modal-root')).to_be_empty()
            expect(page.locator('#main-content h1')).to_have_text('Your money, in focus.')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / 'dashboard-mobile.png'), full_page=True)
            print('PASS: responsive mobile navigation, list and bottom-sheet modal')
            assert not errors, errors
            browser.close()
            print('All browser smoke checks passed; no uncaught JavaScript errors.')
    finally:
        process.terminate()
        process.wait(timeout=10)
