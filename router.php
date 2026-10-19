<?php
declare(strict_types=1);
// Optional router: php -S localhost:8000 router.php. Never expose private files.
$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
$path = rawurldecode(is_string($path) ? $path : '/');
$public = realpath(__DIR__ . '/public');
$file = realpath(__DIR__ . '/public' . ($path === '/' ? '/index.php' : $path));
if (!$public || !$file || !str_starts_with($file, $public . DIRECTORY_SEPARATOR) || !is_file($file)) {
    http_response_code(404);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Not found';
    return;
}
if (pathinfo($file, PATHINFO_EXTENSION) === 'php') {
    require $file;
    return;
}
$types = ['css' => 'text/css; charset=utf-8', 'js' => 'application/javascript; charset=utf-8', 'svg' => 'image/svg+xml', 'png' => 'image/png', 'ico' => 'image/x-icon'];
$extension = strtolower(pathinfo($file, PATHINFO_EXTENSION));
if (!isset($types[$extension])) {
    http_response_code(404);
    return;
}
header('Content-Type: ' . $types[$extension]);
header('X-Content-Type-Options: nosniff');
readfile($file);
