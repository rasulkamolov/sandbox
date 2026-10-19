<?php
// Keep this preflight compatible with older PHP so an unsupported host gets a
// readable response before loading the PHP 8.2 application classes.
final class Hosting
{
    public static function problems(): array
    {
        $issues = [];
        if (PHP_VERSION_ID < 80200) {
            $issues[] = 'This application needs PHP 8.2 or newer. This hosting account is using PHP ' . PHP_VERSION . '.';
        }
        if (!class_exists('PDO') || !in_array('sqlite', PDO::getAvailableDrivers(), true)) {
            $issues[] = 'The hosting PHP runtime does not provide PDO SQLite. The database uses this native PHP capability; no framework or plugin is needed.';
        }
        if (!function_exists('session_start')) {
            $issues[] = 'PHP sessions are unavailable on this hosting account.';
        }
        if (!function_exists('json_encode')) {
            $issues[] = 'PHP JSON support is unavailable on this hosting account.';
        }
        foreach (['config/config.php', 'src/Auth.php', 'src/Database.php', 'src/Finance.php', 'src/Helpers.php', 'lang/en.php', 'lang/uz.php', 'lang/ru.php', 'public/assets/app.css', 'public/assets/app.js', 'public/assets/vendor/lucide.min.js', 'public/assets/vendor/chart.umd.min.js'] as $file) {
            if (!is_readable(dirname(__DIR__) . '/' . $file)) {
                $issues[] = 'The upload is incomplete: ' . $file . ' is missing or unreadable. Extract all files from the upload ZIP again; your existing database is not included in the ZIP.';
            }
        }
        $path = getenv('FINANCE_DB_PATH') ?: dirname(__DIR__) . '/database/finance.db';
        $directory = dirname($path);
        if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) {
            $issues[] = 'PHP cannot create the database directory. The application folder must be writable by your hosting PHP process.';
        } elseif (!is_writable($directory) || (is_file($path) && !is_writable($path))) {
            $issues[] = 'PHP cannot write to database/. Allow the hosting PHP user to write to that directory and its existing database file. Existing data will not be replaced.';
        }
        return $issues;
    }

    public static function cookiePath(): string
    {
        $directory = str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/api.php'));
        $directory = trim($directory, '/');
        if ($directory === '') return '/';
        $segments = [];
        foreach (explode('/', $directory) as $segment) {
            $segments[] = rawurlencode(rawurldecode($segment));
        }
        return '/' . implode('/', $segments) . '/';
    }

    public static function errorPage(array $issues): void
    {
        http_response_code(503);
        header('Content-Type: text/html; charset=utf-8');
        header('Cache-Control: no-store');
        $items = '';
        foreach ($issues as $issue) {
            $items .= '<li>' . htmlspecialchars($issue, ENT_QUOTES, 'UTF-8') . '</li>';
        }
        echo '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            . '<title>Vela — hosting check</title><style>body{margin:0;padding:48px 24px;background:#090d16;color:#e2e8f0;font:16px/1.7 system-ui,sans-serif}'
            . 'main{max-width:660px;margin:8vh auto;background:#111827;padding:32px;border:1px solid #1f2937;border-radius:20px}'
            . 'h1{font-size:28px;line-height:1.3}li{margin:16px 0}a{color:#34d399}small{color:#94a3b8}</style>'
            . '<main><small>VELA · HOSTING CHECK</small><h1>Your files uploaded. The hosting runtime needs attention.</h1>'
            . '<ul>' . $items . '</ul><p>No Composer, npm, framework, or application plugins need to be installed.</p>'
            . '<p>Ask your hosting provider to check the native PHP capabilities listed above, then <a href="">reload this page</a>.</p></main></html>';
    }
}
