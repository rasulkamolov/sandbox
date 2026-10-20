#!/usr/bin/env python3
"""Optional Chromium integration tests for all finance mutation forms.
Requires Python playwright and Chromium; isolates database and sessions in /tmp.
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
from datetime import date, timedelta
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PHP = os.environ.get('PHP_BIN', shutil.which('php') or '/workspace/.runtime/php/bin/php')
CHROME = os.environ.get('CHROMIUM_BIN', shutil.which('chromium') or '')

with tempfile.TemporaryDirectory(prefix='vela-forms-') as directory:
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    sessions = Path(directory) / 'sessions'
    sessions.mkdir()
    server_log = open(Path(directory) / 'server.log', 'w+')
    process = subprocess.Popen([PHP, '-S', f'127.0.0.1:{port}', '-t', str(ROOT / 'public')],
        env={**os.environ, 'FINANCE_DB_PATH': str(Path(directory) / 'finance.db'), 'FINANCE_SESSION_PATH': str(sessions)},
        stdout=server_log, stderr=server_log)
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
            form = page.locator('form[data-form=setup]')
            password = secrets.token_urlsafe(24)
            form.locator('[name=name]').fill('Form Test Owner')
            form.locator('[name=email]').fill('forms-owner@example.test')
            form.locator('[name=password]').fill(password)
            form.locator('[name=demo]').uncheck()
            form.locator('button[type=submit]').click()
            expect(page.locator('#main-content h1')).to_have_text('Your money, in focus.')

            def data():
                result = page.request.get(base + '/api.php?action=bootstrap').json()
                assert result.get('ok'), result
                return result['data']

            def item(resource, **fields):
                return next(row for row in data()[resource] if all(row.get(key) == value for key, value in fields.items()))

            def balance(account_id):
                return item('accounts', id=account_id)['current_balance']

            def navigate(route):
                page.locator(f'#sidebar [data-page="{route}"]').click()
                expect(page.locator('#main-content h1')).to_be_visible()

            def new(resource, action, route=None):
                if route:
                    navigate(route)
                page.locator(f'#main-content [data-action="new-{action}"]').first.click()
                return page.locator(f'form[data-resource="{resource}"]')

            def edit(resource, entry_id):
                page.locator(f'#main-content [data-action=edit][data-resource="{resource}"][data-id="{entry_id}"]').click()
                return page.locator(f'form[data-resource="{resource}"]')

            def submit(form):
                form.locator('button[type=submit]').click()
                try:
                    expect(page.locator('#modal-root')).to_be_empty(timeout=6000)
                except AssertionError:
                    error = page.locator('#modal-root .form-error')
                    raise AssertionError('Form failed: ' + (error.inner_text() if error.count() else page.locator('#modal-root').inner_text()))

            def delete(resource, entry_id):
                page.locator(f'#main-content [data-action=delete][data-resource="{resource}"][data-id="{entry_id}"]').click()
                page.locator('[data-action=confirm-delete]').click()
                expect(page.locator('#modal-root')).to_be_empty()

            account_ids = []
            for name, currency, opening in [('Form USD source', 'USD', '1000'), ('Form USD destination', 'USD', '100'), ('Form UZS destination', 'UZS', '100000')]:
                form = new('accounts', 'account', 'accounts')
                form.locator('[name=name]').fill(name)
                form.locator('[name=type]').select_option('bank')
                form.locator('[name=currency]').select_option(currency)
                form.locator('[name=initial_balance]').fill(opening)
                submit(form)
                account_ids.append(item('accounts', name=name)['id'])
            source, destination, uzs = account_ids
            print('PASS: three account forms in separate currencies')

            # Category hierarchy and tag create/update/delete via real forms.
            form = new('categories', 'category', 'categories')
            form.locator('[name=name]').fill('Form office')
            submit(form)
            parent = item('categories', name='Form office')['id']
            form = new('categories', 'category')
            form.locator('[name=name]').fill('Form software')
            form.locator('[name=parent_id]').select_option(str(parent))
            submit(form)
            child = item('categories', name='Form software')['id']
            assert item('categories', id=child)['parent_id'] == parent
            form = edit('categories', child)
            form.locator('[name=name]').fill('Form software updated')
            submit(form)
            form = new('tags', 'tag')
            form.locator('[name=name]').fill('Form tag')
            submit(form)
            tag = item('tags', name='Form tag')['id']
            form = edit('tags', tag)
            form.locator('[name=name]').fill('Form tag updated')
            submit(form)
            assert item('tags', id=tag)['name'] == 'Form tag updated'
            delete('tags', tag)
            assert not any(row['id'] == tag for row in data()['tags'])
            print('PASS: category hierarchy and tag create/update/delete')

            form = new('budgets', 'budget', 'budgets')
            form.locator('[name=category_id]').select_option(str(parent))
            form.locator('[name=amount]').fill('500')
            submit(form)
            budget = item('budgets', category_id=parent)['id']
            form = edit('budgets', budget)
            form.locator('[name=amount]').fill('600')
            submit(form)
            assert item('budgets', id=budget)['amount'] == 600
            delete('budgets', budget)
            assert not any(row['id'] == budget for row in data()['budgets'])
            print('PASS: budget create/update/delete')

            form = new('transfers', 'transfer', 'transfers')
            form.locator('[name=from_account_id]').select_option(str(source))
            form.locator('[name=to_account_id]').select_option(str(destination))
            form.locator('[name=amount]').fill('100')
            form.locator('[name=fee]').fill('2')
            form.locator('[name=description]').fill('Form same currency')
            submit(form)
            transfer = item('transfers', description='Form same currency')['id']
            assert balance(source) == 898 and balance(destination) == 200
            form = edit('transfers', transfer)
            form.locator('[name=amount]').fill('120')
            form.locator('[name=fee]').fill('3')
            submit(form)
            assert balance(source) == 877 and balance(destination) == 220
            form = new('transfers', 'transfer')
            form.locator('[name=from_account_id]').select_option(str(source))
            form.locator('[name=to_account_id]').select_option(str(uzs))
            expect(form.locator('[name=received_amount]')).to_be_visible()
            form.locator('[name=amount]').fill('10')
            form.locator('[name=received_amount]').fill('126000')
            form.locator('[name=fee]').fill('0.50')
            form.locator('[name=description]').fill('Form cross currency')
            submit(form)
            cross = item('transfers', description='Form cross currency')['id']
            assert balance(source) == 866.5 and balance(uzs) == 226000
            delete('transfers', cross)
            delete('transfers', transfer)
            assert balance(source) == 1000 and balance(destination) == 100 and balance(uzs) == 100000
            print('PASS: transfer create/update/delete and explicit cross-currency settlement')

            form = new('debts', 'debt', 'debts')
            form.locator('[name=direction]').select_option('lending')
            form.locator('[name=counterparty]').fill('Form client')
            form.locator('[name=amount]').fill('200')
            form.locator('[name=account_id]').select_option(str(source))
            form.locator('[name=due_date]').fill((date.today() + timedelta(days=7)).isoformat())
            submit(form)
            debt_id = item('debts', counterparty='Form client')['id']
            assert balance(source) == 800
            page.locator(f'[data-action=repayment][data-id="{debt_id}"]').click()
            form = page.locator('form[data-form=repayment]')
            form.locator('[name=amount]').fill('50')
            form.locator('[name=account_id]').select_option(str(source))
            submit(form)
            assert balance(source) == 850 and item('debts', id=debt_id)['remaining'] == 150
            payment_id = item('debts', id=debt_id)['payments'][0]['id']
            page.locator(f'[data-action=debt-history][data-id="{debt_id}"]').click()
            page.locator(f'[data-action=edit-repayment][data-id="{payment_id}"]').click()
            form = page.locator('form[data-form=repayment]')
            form.locator('[name=amount]').fill('75')
            submit(form)
            assert balance(source) == 875 and item('debts', id=debt_id)['remaining'] == 125
            page.locator(f'[data-action=debt-history][data-id="{debt_id}"]').click()
            page.locator(f'[data-action=delete][data-resource=repayments][data-id="{payment_id}"]').click()
            page.locator('[data-action=confirm-delete]').click()
            expect(page.locator('#modal-root')).to_be_empty()
            assert balance(source) == 800 and item('debts', id=debt_id)['remaining'] == 200
            form = edit('debts', debt_id)
            form.locator('[name=amount]').fill('250')
            form.locator('[name=contact]').fill('client@example.test')
            submit(form)
            assert balance(source) == 750, (balance(source), item('debts', id=debt_id))
            delete('debts', debt_id)
            assert balance(source) == 1000
            print('PASS: debt and repayment create/update/delete with balance reconciliation')

            form = new('recurring', 'recurring', 'recurring')
            form.locator('[name=amount]').fill('10')
            form.locator('[name=account_id]').select_option(str(source))
            form.locator('[name=category_id]').select_option(str(child))
            form.locator('[name=description]').fill('Form scheduled expense')
            form.locator('[name=next_date]').fill(date.today().isoformat())
            submit(form)
            recurring_id = item('recurring', description='Form scheduled expense')['id']
            page.locator('[data-action=process-recurring]').click()
            expect(page.locator('[data-action=process-recurring]')).to_be_enabled()
            assert balance(source) == 990
            assert item('recurring', id=recurring_id)['next_date'] > date.today().isoformat()
            form = edit('recurring', recurring_id)
            form.locator('[name=enabled]').select_option('0')
            form.locator('[name=frequency]').select_option('weekly')
            submit(form)
            assert item('recurring', id=recurring_id)['enabled'] == 0
            delete('recurring', recurring_id)
            navigate('transactions')
            generated = item('transactions', description='Form scheduled expense')['id']
            delete('transactions', generated)
            assert balance(source) == 1000
            navigate('categories')
            delete('categories', child)
            delete('categories', parent)
            print('PASS: recurring create/update/process/delete and category deletion')

            assistant_password = secrets.token_urlsafe(24)
            form = new('users', 'user', 'settings')
            form.locator('[name=name]').fill('Form assistant')
            form.locator('[name=email]').fill('forms-assistant@example.test')
            form.locator('[name=password]').fill(assistant_password)
            submit(form)
            assistant_id = item('users', email='forms-assistant@example.test')['id']
            form = edit('users', assistant_id)
            form.locator('[name=active]').select_option('0')
            submit(form)
            assert item('users', id=assistant_id)['active'] == 0
            replacement_password = secrets.token_urlsafe(24)
            form = edit('users', assistant_id)
            form.locator('[name=name]').fill('Form assistant updated')
            form.locator('[name=active]').select_option('1')
            form.locator('[name=password]').fill(replacement_password)
            submit(form)
            assert item('users', id=assistant_id)['active'] == 1
            assert page.locator(f'[data-action=delete][data-resource=users][data-id="{assistant_id}"]').count() == 0
            print('PASS: assistant creation, deactivation, reactivation and password reset')

            new_password = secrets.token_urlsafe(24)
            form = page.locator('form[data-form=password]')
            form.locator('[name=current_password]').fill(password)
            form.locator('[name=new_password]').fill(new_password)
            form.locator('[name=confirm_password]').fill(new_password)
            form.locator('button[type=submit]').click()
            expect(page.locator('#toast-root')).to_contain_text('Password updated')
            # A following mutation demonstrates the rotated CSRF is installed.
            form = new('tags', 'tag', 'categories')
            form.locator('[name=name]').fill('After password rotation')
            submit(form)
            assert item('tags', name='After password rotation')
            page.locator('#logout-button').click()
            form = page.locator('form[data-form=login]')
            expect(form).to_be_visible()
            form.locator('[name=email]').fill('forms-assistant@example.test')
            form.locator('[name=password]').fill(replacement_password)
            form.locator('button[type=submit]').click()
            expect(page.locator('#main-content h1')).to_have_text('Transactions')
            expect(page.locator('#sidebar [data-page=accounts]')).to_be_hidden()
            expect(page.locator('#sidebar [data-page=reports]')).to_be_hidden()
            assistant_data = data()
            assert 'summary' not in assistant_data and 'analytics' not in assistant_data
            assert all('current_balance' not in account for account in assistant_data['accounts'])
            print('PASS: password change, CSRF rotation, assistant login and private-balance restrictions')

            assert not errors, errors
            browser.close()
            print('All extended form checks passed; no uncaught JavaScript errors.')
    finally:
        process.terminate()
        process.wait(timeout=10)
        server_log.close()
