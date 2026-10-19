#!/usr/bin/env python3
"""Exercise an unchanged upload in subfolders, without rewrites or a router.

Optional development test: requires Python Playwright and Chromium. Set PHP_BIN
and CHROMIUM_BIN if they are not on PATH. Application files, database and session
storage are copied/created in a temporary directory; real financial data is never
used. PHP's server does not enforce .htaccess, so Apache access controls are not
tested here.
"""
from contextlib import contextmanager
import csv
import io
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PHP = os.environ.get('PHP_BIN') or shutil.which('php') or '/workspace/.runtime/php/bin/php'
CHROME = os.environ.get('CHROMIUM_BIN') or shutil.which('chromium') or ''


def copy_application(destination):
    destination.mkdir(parents=True)
    for directory in ('config', 'src', 'lang', 'public'):
        shutil.copytree(ROOT / directory, destination / directory)
    for filename in ('index.php', '.htaccess'):
        source = ROOT / filename
        if source.exists():
            shutil.copy2(source, destination / filename)
    (destination / 'database').mkdir()


@contextmanager
def uploaded_server(mount, public_root=False, independent_databases=False):
    """Copy deployable source into a plain host's document root."""
    with tempfile.TemporaryDirectory(prefix='vela-deployment-') as temporary:
        folder = Path(temporary)
        document_root = folder / 'www'
        app = document_root / mount
        copy_application(app)
        sessions = folder / 'sessions'
        sessions.mkdir()
        database = app / 'database/finance.db' if independent_databases else folder / 'test-finance.db'
        environment = {**os.environ, 'FINANCE_DB_PATH': '' if independent_databases else str(database), 'FINANCE_SESSION_PATH': str(sessions)}
        preflight = subprocess.run(
            [PHP, '-r', 'require $argv[1]; echo realpath(dirname(DATABASE_PATH)), DIRECTORY_SEPARATOR, basename(DATABASE_PATH);', str(app / 'config/config.php')],
            env=environment, capture_output=True, text=True, timeout=15,
        )
        assert preflight.returncode == 0 and preflight.stdout.strip() == str(database), (
            'Refusing to run: isolated FINANCE_DB_PATH was not accepted.', preflight.stderr
        )
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        if public_root:
            document_root = app / 'public'
            public_path = '/'
            entry_path = '/'
        else:
            entry_path = '/' + quote(mount, safe='/') + '/'
            public_path = entry_path + 'public/'
        with (folder / 'php.log').open('w+', encoding='utf-8') as log:
            server = subprocess.Popen(
                [PHP, '-S', f'127.0.0.1:{port}', '-t', str(document_root)],
                cwd=app, env=environment, stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise RuntimeError('PHP server exited during startup.')
                    try:
                        with urlopen(origin + public_path + 'api.php?action=session', timeout=1) as response:
                            assert response.status == 200
                        break
                    except OSError:
                        time.sleep(0.05)
                else:
                    raise RuntimeError('PHP server did not become ready.')
                assert database.is_file(), 'Isolated database was not initialized.'
                yield origin, entry_path, public_path, folder
            except BaseException:
                log.flush()
                log.seek(0)
                print(log.read()[-8000:])
                raise
            finally:
                server.terminate()
                server.wait(timeout=10)


def assert_api(page, api_url, action='bootstrap'):
    response = page.request.get(api_url + '?action=' + action)
    assert response.status == 200, (response.status, response.text())
    payload = response.json()
    assert payload.get('ok'), payload
    return payload['data']


def submit(page, form):
    form.locator('button[type=submit]').click()
    expect(page.locator('#modal-root')).to_be_empty(timeout=7000)


def delete(page, resource, entry_id):
    page.locator(f'#main-content [data-action=delete][data-resource={resource}][data-id="{entry_id}"]').click()
    page.locator('[data-action=confirm-delete]').click()
    expect(page.locator('#modal-root')).to_be_empty(timeout=7000)


def failure_and_retry(page, public_url, action, recovered_selector):
    """A host's HTML 403 must produce a working recovery screen."""
    def intercept(route):
        if parse_qs(urlsplit(route.request.url).query).get('action') == [action]:
            route.fulfill(status=403, content_type='text/html', body='<h1>Forbidden by host</h1>')
        else:
            route.continue_()

    pattern = '**/api.php?*'
    page.route(pattern, intercept)
    page.goto(public_url, wait_until='networkidle')
    expect(page.locator('#auth-root .initial-error')).to_be_visible()
    expect(page.locator('#auth-root .initial-error p')).not_to_be_empty()
    expect(page.locator('[data-action=retry]')).to_be_enabled()
    expect(page.locator('.initial-loading')).to_have_count(0)
    page.unroute(pattern, intercept)
    page.locator('[data-action=retry]').click()
    expect(page.locator(recovered_selector)).to_be_visible(timeout=7000)


def timeout_and_retry(page, public_url):
    """A request that never returns must stop loading without a manual refresh."""
    stalled = []

    def intercept(route):
        if parse_qs(urlsplit(route.request.url).query).get('action') == ['session']:
            stalled.append(route)
        else:
            route.continue_()

    pattern = '**/api.php?*'
    page.route(pattern, intercept)
    page.goto(public_url, wait_until='domcontentloaded')
    expect(page.locator('#auth-root .initial-error')).to_be_visible(timeout=22000)
    expect(page.locator('#auth-root .initial-error p')).to_contain_text('too long to respond')
    expect(page.locator('[data-action=retry]')).to_be_enabled()
    assert stalled, 'The timeout test never intercepted a session request.'
    for route in stalled:
        route.abort()
    page.unroute(pattern, intercept)
    page.locator('[data-action=retry]').click()
    expect(page.locator('form[data-form=setup]')).to_be_visible(timeout=7000)


def exercise_upload(browser, mount, full=True, public_root=False, storage_disabled=False):
    with uploaded_server(mount, public_root) as (origin, entry_path, public_path, temporary):
        public_url = origin + public_path
        api_url = public_url + 'api.php'
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
        if storage_disabled:
            context.add_init_script("""Object.defineProperty(window, 'localStorage', {
                get() { throw new DOMException('Browser storage is disabled', 'SecurityError'); }
            });""")
        page = context.new_page()
        requests = []
        errors = []
        page.on('request', lambda request: requests.append(request.url))
        page.on('pageerror', lambda error: errors.append(str(error)))

        # Use the actual upload URL. No test router or response URL rewriting.
        page.goto(origin + entry_path, wait_until='networkidle')
        expect(page).to_have_url(public_url)
        expect(page.locator('form[data-form=setup]')).to_be_visible()
        session_cookies = [cookie for cookie in context.cookies() if cookie['name'].endswith('_session')]
        assert len(session_cookies) == 1, session_cookies
        assert session_cookies[0]['path'] == public_path, session_cookies
        assert session_cookies[0]['httpOnly'] and session_cookies[0]['sameSite'] == 'Lax'
        assert page.evaluate("getComputedStyle(document.body).backgroundColor") == 'rgb(9, 13, 22)'
        assert page.locator('.auth-logo .brand-mark').bounding_box()['width'] < 100
        assert page.evaluate('!!window.Chart && !!window.lucide')
        assert page.locator('svg.lucide').count() > 5
        for resource in page.locator('link[rel=stylesheet], script[src]').evaluate_all(
            '(elements) => elements.map(element => element.href || element.src)'
        ):
            assert resource.startswith(public_url + 'assets/'), resource
            response = page.request.get(resource)
            assert response.status == 200, (resource, response.status)
            content_type = response.headers.get('content-type', '')
            assert ('text/css' in content_type if urlsplit(resource).path.endswith('.css') else 'javascript' in content_type), (resource, content_type)
        assert page.locator('.auth-logo').evaluate('(element) => element.href').startswith(public_url)

        # Both conventional entry paths must be valid on a plain file host.
        if not public_root:
            page.goto(origin + entry_path + 'index.php', wait_until='networkidle')
            expect(page).to_have_url(public_url)
        page.goto(public_url + 'index.php', wait_until='networkidle')
        expect(page.locator('form[data-form=setup]')).to_be_visible()
        if full:
            failure_and_retry(page, public_url, 'session', 'form[data-form=setup]')
            timeout_and_retry(page, public_url)

        setup = page.locator('form[data-form=setup]')
        setup.locator('[name=name]').fill('Upload Test Owner')
        setup.locator('[name=email]').fill('upload-owner@example.test')
        setup.locator('[name=password]').fill(secrets.token_urlsafe(24))
        setup.locator('[name=demo]').uncheck()
        setup.locator('button[type=submit]').click()
        expect(page.locator('#main-content h1')).to_have_text('Your money, in focus.', timeout=7000)
        assert assert_api(page, api_url, 'session')['user']['role'] == 'owner'
        assert not assert_api(page, api_url)['accounts'], 'Sample data was unexpectedly installed.'
        if storage_disabled:
            page.locator('#theme-toggle').click()
            expect(page.locator('html')).to_have_attribute('data-theme', 'light')
            page.locator('#theme-toggle').click()
            expect(page.locator('html')).to_have_attribute('data-theme', 'dark')

        # Header and translation endpoint must retain the full deployment prefix.
        page.locator('#language-select').select_option('uz')
        expect(page.locator('html')).to_have_attribute('lang', 'uz')
        assert assert_api(page, api_url, 'session')['locale'] == 'uz'
        page.reload(wait_until='networkidle')
        expect(page.locator('html')).to_have_attribute('lang', 'uz')
        page.locator('#language-select').select_option('en')
        expect(page.locator('html')).to_have_attribute('lang', 'en')
        page.locator('#sidebar .brand').click()
        expect(page).to_have_url(public_url)
        expect(page.locator('#main-content h1')).to_have_text('Your money, in focus.')

        if full:
            page.locator('#sidebar [data-page=accounts]').click()
            page.locator('#main-content [data-action=new-account]').first.click()
            form = page.locator('form[data-resource=accounts]')
            form.locator('[name=name]').fill('Uploaded cash wallet')
            form.locator('[name=type]').select_option('cash')
            form.locator('[name=currency]').select_option('USD')
            form.locator('[name=initial_balance]').fill('100')
            submit(page, form)
            account = next(row for row in assert_api(page, api_url)['accounts'] if row['name'] == 'Uploaded cash wallet')
            assert account['current_balance'] == 100
            account_id = account['id']
            page.locator(f'[data-action=edit][data-resource=accounts][data-id="{account_id}"]').click()
            form = page.locator('form[data-resource=accounts]')
            form.locator('[name=initial_balance]').fill('150')
            submit(page, form)

            def balance():
                return next(row['current_balance'] for row in assert_api(page, api_url)['accounts'] if row['id'] == account_id)

            assert balance() == 150
            page.locator('#quick-add').click()
            form = page.locator('form[data-resource=transactions]')
            form.locator('[name=account_id]').select_option(str(account_id))
            form.locator('[name=amount]').fill('12.34')
            form.locator('[name=description]').fill('Uploaded transaction')
            submit(page, form)
            assert balance() == 137.66
            transaction = next(row for row in assert_api(page, api_url)['transactions'] if row['description'] == 'Uploaded transaction')
            page.locator('#sidebar [data-page=transactions]').click()
            page.locator(f'[data-action=edit][data-resource=transactions][data-id="{transaction["id"]}"]').click()
            form = page.locator('form[data-resource=transactions]')
            form.locator('[name=amount]').fill('20')
            submit(page, form)
            assert balance() == 130

            export = page.locator('#main-content a[download]').first
            assert export.evaluate('(element) => element.href').startswith(api_url + '?')
            with page.expect_download() as download_event:
                export.click()
            download = download_event.value
            assert not download.failure()
            records = list(csv.DictReader(io.StringIO(Path(download.path()).read_text(encoding='utf-8-sig'))))
            assert any(row.get('description') == 'Uploaded transaction' and float(row['amount']) == 20 for row in records)

            page.locator('#sidebar [data-page=settings]').click()
            backup = page.locator('#main-content a[download]')
            assert backup.evaluate('(element) => element.href').startswith(api_url + '?')
            with page.expect_download() as download_event:
                backup.click()
            download = download_event.value
            assert not download.failure()
            backup_path = temporary / 'downloaded.db'
            download.save_as(backup_path)
            assert backup_path.read_bytes().startswith(b'SQLite format 3\x00')
            with sqlite3.connect(backup_path) as database:
                assert database.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert database.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 1

            page.locator('#sidebar [data-page=transactions]').click()
            delete(page, 'transactions', transaction['id'])
            assert balance() == 150
            page.locator('#sidebar [data-page=accounts]').click()
            delete(page, 'accounts', account_id)
            assert not assert_api(page, api_url)['accounts']
            failure_and_retry(page, public_url, 'bootstrap', '#main-content h1')
            expect(page.locator('#main-content h1')).to_have_text('Your money, in focus.')

        expected_prefix = public_path
        same_origin = [url for url in requests if url.startswith(origin + '/')]
        assert not [url for url in requests if urlsplit(url).scheme in ('http', 'https') and not url.startswith(origin + '/')], 'External runtime dependency requested.'
        for url in same_origin:
            path = urlsplit(url).path
            if path.endswith(('/api.php', '/i18n.php', '.css', '.js')):
                assert path.startswith(expected_prefix), f'Request escaped deployment directory: {url}'
        assert any(urlsplit(url).path == public_path + 'api.php' for url in same_origin)
        assert any(urlsplit(url).path == public_path + 'i18n.php' for url in same_origin)
        assert not errors, errors
        context.close()
        print(f'PASS: {entry_path} (plain PHP document root, {"full CRUD/download/recovery" if full else "onboarding/assets/session/language"})')


def exercise_cookie_isolation(browser):
    """Two unchanged copies on one hostname keep their data and logins separate."""
    with uploaded_server('first', independent_databases=True) as (origin, _, first_path, temporary):
        copy_application(temporary / 'www/second')
        context = browser.new_context()
        first_api = origin + first_path + 'api.php'
        second_api = origin + '/second/public/api.php'

        def create_owner(api, name, email):
            session = assert_api(context, api, 'session')
            assert session['needs_setup'] and session['user'] is None
            response = context.request.post(api + '?action=setup', data={
                'name': name, 'email': email, 'password': secrets.token_urlsafe(24), 'demo': False,
            }, headers={'X-CSRF-Token': session['csrf']})
            assert response.status == 201, response.text()
            assert response.json()['data']['user']['name'] == name

        create_owner(first_api, 'First installation', 'first@example.test')
        create_owner(second_api, 'Second installation', 'second@example.test')
        assert assert_api(context, first_api, 'session')['user']['name'] == 'First installation'
        assert assert_api(context, second_api, 'session')['user']['name'] == 'Second installation'
        cookies = [cookie for cookie in context.cookies() if cookie['name'].endswith('_session')]
        assert len(cookies) == 2 and len({cookie['name'] for cookie in cookies}) == 2, cookies
        assert {cookie['path'] for cookie in cookies} == {'/first/public/', '/second/public/'}, cookies
        for install, email in [('first', 'first@example.test'), ('second', 'second@example.test')]:
            with sqlite3.connect(temporary / 'www' / install / 'database/finance.db') as database:
                assert database.execute('SELECT email FROM users').fetchall() == [(email,)]
        context.close()
        print('PASS: two uploads on the same hostname have separate cookie names, cookie paths, sessions and databases')


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            **({'executable_path': CHROME} if CHROME else {}), headless=True, args=['--no-sandbox'],
        )
        try:
            exercise_upload(browser, 'sandbox')
            exercise_upload(browser, 'clients/finance vault', full=False, storage_disabled=True)
            exercise_upload(browser, 'standalone', full=False, public_root=True)
            exercise_cookie_isolation(browser)
        finally:
            browser.close()
    print('All upload-deployment checks passed; no external requests or uncaught JavaScript errors.')


if __name__ == '__main__':
    main()
