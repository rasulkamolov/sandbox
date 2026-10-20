# Vela — personal & business finance

A self-contained finance workspace built with PHP 8.2+, PDO SQLite, Vanilla ES6, and custom responsive CSS. No PHP framework, Composer, build system, or JavaScript package installation is required. Pinned Chart.js and Lucide distributions are vendored from their CDN releases, so the interface needs no external requests; financial data stays in your SQLite database.

## Upload to your website

Use the prepared **`vela-upload.zip`** to deploy from your hosting file manager. Extract its contents into `public_html/sandbox/` and open **https://oxfordlc.uz/sandbox/**. The root entry point opens the application in `/sandbox/public/`; assets, API requests, translations and downloads automatically follow the installation folder.

The upload includes local CSS, icons and charts. There is no dependency installation, build command, Composer, npm, plugin, rewrite rule or document-root change to perform. Standard Apache/LiteSpeed hosting must already provide **PHP 8.2+ with PDO SQLite, session and JSON support**, allow the included `.htaccess` protections, and let PHP write to `database/`. The application checks its requirements and displays a clear startup message if a host capability is unavailable.

See [the file-manager upload guide](docs/UPLOAD.md) for the exact extraction steps and safe updates. The upload archive contains application files only; it never includes an existing financial database, accounts, passwords, secrets or Git history. When updating, preserve `database/finance.db` and its SQLite journal files.

To generate the upload archive from this source checkout, use Python's standard library:

```sh
python3 scripts/package-upload.py
```

This creates `/tmp/vela-upload.zip`. A destination outside the source checkout can be supplied as the sole argument. Python is a packaging tool for the developer; the uploaded application runs entirely in PHP.

## Run locally

Use PHP 8.2 or newer with **PDO SQLite**, **session**, and **JSON** enabled. On Debian/Ubuntu, the PDO SQLite driver is provided by `php-sqlite3`.

```sh
php scripts/check.php
php -S localhost:8000 -t public
```

Alternatively, from the `public/` directory run exactly:

```sh
php -S localhost:8000
```

An optional secure development router supports `php -S localhost:8000 router.php` from the repository root. For PHP's built-in server, use the public document root or this router: the development server does not apply `.htaccess` protections. File-manager deployments use Apache/LiteSpeed and the included access rules.

Open the server in your browser, create your owner account, and choose whether to include sample financial data. There are no default credentials. Passwords must be 12–72 bytes. Leave sample data unchecked for an empty real workspace. The database and schema initialize automatically at `database/finance.db`; keep this directory writable by the PHP process.

On this prepared cloud machine PHP is available at `/workspace/.runtime/php/bin/php`. `sh scripts/setup-runtime.sh` validates an existing PHP installation or installs an unprivileged PHP runtime from signed Debian repositories when needed. Runtime files live outside the repository.

## Finance workflows

- **Accounts:** bank, card, cash, savings and digital wallets; UZS, USD, EUR and RUB; opening balances, metadata, targets, colors, archive status, and account history.
- **Transactions:** income and expense records, categories, tags, receipt references, date and search filters, CSV export, and immediate balance recalculation.
- **Transfers:** editable transfers with optional fees, posted atomically. Cross-currency transfers require the explicit amount received in the destination currency; the app never invents an exchange rate.
- **Budgets:** monthly category caps with green, amber, and red thresholds.
- **Debts:** borrowing and lending, counterparty contact and due dates, account-linked principal movements, and partial repayments. Repayments cannot exceed the remaining debt.
- **Recurring:** daily, weekly, monthly and annual schedules; process due entries from the interface. Processing is idempotent. Process due entries from the UI or schedule the local CLI worker below; there is no bundled background daemon.
- **Reports:** filter by period, currency and account; compare income, spending, net cash flow and savings rate with the previous period of the same length. See ranked spending categories, transfer fees, account performance, the largest expenses, overdue and upcoming obligations, daily spending and estimated balance runway. Charts include accessible data tables and a CSV export of the selected report. The 30/60/90-day forecast is explicitly for all accounts in the selected currency. Forecasts are estimates, not guaranteed outcomes.
- **Settings:** session-persisted English, Uzbek and Russian; dark/light themes; current-password-verified password changes; assistant management; audit history; and a consistent SQLite backup download.

## Readability and a fresh start

The interface uses a 16px base, readable chart labels, and layouts for phones, tablets, landscape screens and desktops. On phones, records become cards, navigation stays within thumb reach, and forms open as keyboard-aware bottom sheets with sticky save actions. The More menu includes language, theme and sign-out controls. Reports offer section shortcuts; choose Custom dates to reveal the date range on mobile.

Owners can use **Settings → Remove sample data** to remove explicitly marked example records. Real entries are preserved. If a real entry still uses a sample account, category, tag, schedule or debt, that required context is retained. A sample record you edit becomes a real record. A retained account keeps its opening balance; you can review it under Accounts.

For a completely empty financial workspace, use **Settings → Reset financial workspace**. This deletes **all financial records**, including real entries, across every account and currency. Owner/assistant logins, passwords, session language, and the immutable audit history remain. Both actions require the owner's current password and the exact confirmation phrase shown in the dialog. Download a backup first if you might need the old records.

Older uploads did not mark sample records. The update never guesses based on names or amounts: it preserves unmarked records. To remove older samples and start empty, use the explicitly confirmed full financial reset. Updating the application alone never clears financial data.

## Roles and security

The owner controls the whole workspace. Assistants have an operational view for daily transactions, income, expenses, categories, tags and recurring records. Private account balances, net worth, transfers, debts, budgets, reports, assistant management, database backups and audit history are owner-only. Permissions are enforced at the API, not just by hiding navigation.

Sessions use HttpOnly, SameSite=Lax cookies, strict session handling, session ID rotation and idle expiration. HTTPS requests receive Secure cookies. All mutations, including login and onboarding, require the session CSRF token. Passwords use bcrypt; password changes and login resets invalidate older authenticated sessions. Login attempts are rate limited in SQLite. SQL values use prepared statements and financial writes use database transactions. Audit records are append-only through the API.

Monetary values are stored as integer hundredths for all supported currencies, including UZS. UI/API amounts use decimal major units. SQLite foreign keys and WAL are enabled. The application is a single-workspace product with an owner and assistants, rather than a multi-tenant hosting service.

The first-run setup endpoint is accessible until an owner is created. Initialize the owner before exposing a new deployment to an untrusted network. Receipt fields are references/notes; the app does not host uploaded receipt documents.

## Layout

```text
config/           configuration, PDO connection and schema
src/              authentication, database and financial helpers
lang/             English, Uzbek, Russian PHP dictionaries
public/           document root: index.php, api.php, i18n.php and assets
public/assets/    custom CSS and Vanilla JavaScript
scripts/          prerequisite checks and optional cloud runtime setup
tests/            isolated end-to-end HTTP/API integration tests
database/         private, automatically initialized SQLite data
index.php         file-manager deployment entry point
.htaccess         Apache/LiteSpeed access protection; no URL rewriting
router.php        optional safe development router
```

## Validation

```sh
php scripts/check.php
python3 tests/integration.py
```

Set `PHP_BIN` to a nonstandard PHP executable when needed:

```sh
PHP_BIN=/workspace/.runtime/php/bin/php python3 tests/integration.py
```

The integration suite launches a temporary local server and an isolated database via `FINANCE_DB_PATH`; it does not modify your financial database. It exercises authentication, role boundaries, CSRF, account balances, transfer reversals, debts, recurrence, exports and backup integrity.

Optional real browser checks use Python Playwright and Chromium (test tools only):

```sh
PHP_BIN=/workspace/.runtime/php/bin/php python3 tests/browser_smoke.py
PHP_BIN=/workspace/.runtime/php/bin/php python3 tests/browser_forms.py
PHP_BIN=/workspace/.runtime/php/bin/php python3 tests/reports_reset.py
PHP_BIN=/workspace/.runtime/php/bin/php python3 tests/browser_reports_reset.py
PHP_BIN=/workspace/.runtime/php/bin/php python3 tests/browser_mobile.py
```

Set `CHROMIUM_BIN` for a nonstandard Chromium executable. Set `VELA_SCREENSHOT_DIR` to save desktop/mobile screenshots outside the repository. All browser suites use isolated databases. The smoke suite checks onboarding, charts, every module view, transaction CRUD and balance reversals, language/theme persistence, and mobile navigation/modals. The form suite submits all remaining module forms, checks transfers and repayments against real balances, and validates assistant credentials and password/CSRF rotation.

The mobile suite checks every owner page in English, Uzbek and Russian at 320, 375, 430, 768, 844 (landscape), and 1440 pixels. It exercises touch targets, long names and large UZS balances, sidebar/More controls, report filters, form scrolling and transaction create/edit in a reduced keyboard-sized viewport, plus assistant navigation.

## Deployment and operations

PHP's built-in server is intended for development. Standard Apache/LiteSpeed shared hosting supports the file-manager deployment described above with the supplied `.htaccess` files. Preserve these hidden files when extracting or copying the application: they protect the database, source, configuration and private tooling. An Nginx deployment requires equivalent server access rules or a document root at `public/`; Nginx does not apply `.htaccess` files.

For a deployment where you control the server, use a maintained HTTPS web server with its document root at `public/`, disable PHP error display, and restrict filesystem access to the application user. Keep PHP/security updates current. If TLS terminates at a reverse proxy, configure trusted proxy handling so PHP receives the actual HTTPS state; do not blindly trust client-supplied forwarding headers.

Back up using the in-app owner-only backup action so WAL data is included consistently. Treat downloaded backups as sensitive: they contain financial records and password hashes. Encrypt and store them securely. To restore, stop PHP workers, preserve the current database, replace `database/finance.db` from a known backup, remove obsolete `-wal`/`-shm` files only while all workers are stopped, restore owner-only file permissions, and start the service. A backup should be restore-tested before relying on it.

For unattended recurring entries, run the local, CLI-only worker under the same operating system user that owns the database:

```sh
php scripts/process-recurring.php
```

For example, run it every 15 minutes through your host scheduler. It uses the active owner identity for audit attribution and never needs a password or API token. Repeat execution does not duplicate occurrences. The web UI also has a Process due entries action. The app does not fetch bank feeds or current FX rates.

Chart.js and Lucide are served locally; version, source, checksum and license details are in `public/assets/vendor/README.md`. Browser offline caching is not a supported feature. Review `docs/API.md` for the HTTP contract.
