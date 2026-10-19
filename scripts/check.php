<?php
declare(strict_types=1);
$errors = [];
if (PHP_VERSION_ID < 80200) $errors[] = 'PHP 8.2 or newer is required.';
foreach (['pdo_sqlite', 'session', 'json', 'openssl'] as $extension) {
    if (!extension_loaded($extension)) $errors[] = "Missing PHP extension: $extension";
}
$directory = dirname(__DIR__) . '/database';
if (!is_dir($directory) || !is_writable($directory)) $errors[] = 'database/ must be writable by the PHP process.';
foreach ($errors as $error) fwrite(STDERR, "$error\n");
if ($errors) exit(1);
$pdo = new PDO('sqlite::memory:', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$pdo->exec('PRAGMA foreign_keys = ON');
if ((int)$pdo->query('PRAGMA foreign_keys')->fetchColumn() !== 1) exit(1);
printf("Ready: PHP %s, SQLite %s, PDO SQLite and writable database directory.\n", PHP_VERSION, $pdo->query('SELECT sqlite_version()')->fetchColumn());
