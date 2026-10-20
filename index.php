<?php
// File-manager deployment entry point. No rewrite rules or custom document root.
$directory = str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/index.php'));
$segments = [];
foreach (explode('/', trim($directory, '/')) as $segment) {
    if ($segment !== '') $segments[] = rawurlencode(rawurldecode($segment));
}
$target = '/' . ($segments ? implode('/', $segments) . '/' : '') . 'public/';
header('Cache-Control: no-store');
header('Location: ' . $target, true, 302);
exit;
