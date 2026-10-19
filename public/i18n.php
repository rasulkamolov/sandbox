<?php
declare(strict_types=1);

// Translations are public, static resources. This endpoint deliberately does not
// start a session: choosing a locale is persisted by the authenticated API.
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: public, max-age=300, must-revalidate');

if (!in_array($_SERVER['REQUEST_METHOD'] ?? 'GET', ['GET', 'HEAD'], true)) {
    header('Allow: GET, HEAD');
    http_response_code(405);
    echo '{"error":"Method not allowed"}';
    exit;
}

$requested = $_GET['lang'] ?? 'en';
$language = is_string($requested) && in_array($requested, ['en', 'uz', 'ru'], true)
    ? $requested
    : 'en';
header('Content-Language: ' . $language);

$translations = require dirname(__DIR__) . '/lang/' . $language . '.php';
$json = json_encode($translations, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
$etag = '"' . hash('sha256', $json) . '"';
header('ETag: ' . $etag);
if (($_SERVER['HTTP_IF_NONE_MATCH'] ?? '') === $etag) {
    http_response_code(304);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'HEAD') {
    echo $json;
}
