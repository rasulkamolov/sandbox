# Upload Vela with your file manager

## First upload

1. Download **`vela-upload.zip`** from the release or the file provided with this update.
2. Open your hosting file manager and go to the website's `public_html/sandbox/` folder. Create `sandbox` if needed.
3. Upload the ZIP into that folder and choose **Extract**. Its contents must sit directly in `sandbox`, with `index.php`, `public`, `src`, `config` and `database` at the same level. Avoid an extra `sandbox/vela-upload/` or `sandbox/sandbox/` folder.
4. Check that hidden files are shown and that the included `.htaccess` files were extracted. Keep them in place.
5. Delete the uploaded ZIP from the website folder after extraction.
6. Open **https://oxfordlc.uz/sandbox/** and refresh the page. It opens `/sandbox/public/` automatically. Create your owner account; sample data is optional.

The same files also work in a different folder or at the website root. CSS, JavaScript, translations, API requests, CSV exports and database downloads follow that folder automatically. You can open `/sandbox/public/` directly as well.

Everything the browser needs is included: application code, CSS, icons and charts. There are no framework, Composer, npm, plugin or build steps. You do not need to change the site's document root or configure URL rewriting.

## Host requirements

Your hosting account must already support PHP 8.2 or newer with PDO SQLite, sessions and JSON. Standard Apache/LiteSpeed hosting must apply the included `.htaccess` access rules, and PHP must be able to write inside `database/`. These are hosting capabilities; the ZIP cannot supply a PHP runtime or database extension.

Vela checks these requirements before starting and shows a clear message if something is unavailable. If your host reports that PDO SQLite is missing, ask its support to enable the PHP PDO SQLite extension for your website. If database storage is unwritable, ask it to restore the folder's account ownership and normal write permissions. Do not use public-write permissions such as `777`.

The supplied database and configuration protections are designed for Apache/LiteSpeed. If your host uses Nginx without Apache/LiteSpeed, it must provide equivalent access rules or serve only the `public/` folder.

## Updating an existing installation

1. Download a database backup from **Settings → Data backup** when the application is accessible. Store it outside the website folder.
2. Upload the new `vela-upload.zip` into the existing `sandbox/` folder and extract it there. Allow replacement of application files and included `.htaccess` files.
3. Keep the existing `database/` folder, **`database/finance.db`**, and any `finance.db-wal` or `finance.db-shm` files. Do not delete or replace them during the update.
4. Delete the uploaded ZIP and reload **https://oxfordlc.uz/sandbox/**. A hard refresh clears old browser assets if needed.

The supplied archive contains no database or SQLite journal files, so extracting it does not overwrite your financial data or users. A fresh installation initializes its own database automatically. Existing installations keep their owner and assistant logins.

## If the page does not open

- **An oversized logo or an unstyled page:** confirm the complete `public/assets/` folder was extracted and then hard-refresh. The current version resolves these assets relative to the installation folder.
- **A startup error:** follow the specific PHP, session or database message shown on the page. It identifies the required host capability without exposing credentials or internal errors.
- **A 403 or 500 response immediately after upload:** confirm all files were extracted and ask your host whether it supports the bundled Apache/LiteSpeed `.htaccess` access rules. Keep the protection files in place.
- **A folder listing instead of Vela:** open `https://oxfordlc.uz/sandbox/index.php` and confirm the root `index.php` and `.htaccess` were uploaded.

Initialize the owner account promptly on a fresh public installation. There are no default credentials.

## Creating the ZIP from source

This step is for the person preparing an update; it is not required on the hosting account.

```sh
python3 scripts/package-upload.py
```

The output is `/tmp/vela-upload.zip`. To choose another path outside the checkout:

```sh
python3 scripts/package-upload.py /tmp/vela-update.zip
```

The packager uses only Python's standard library. It includes an explicit list of application files and checks every archive entry. Git metadata, financial databases, SQLite journals, credentials, local runtimes, caches and test files are excluded. The optional CLI recurrence worker is included; scheduled processing can be configured later, and due entries can also be processed from the web interface.
