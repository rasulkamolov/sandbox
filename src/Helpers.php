<?php
declare(strict_types=1);

final class ApiException extends RuntimeException
{
    public function __construct(string $message, public readonly int $status = 422) { parent::__construct($message); }
}

function respond(mixed $data, int $status = 200): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => true, 'data' => $data], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE | JSON_THROW_ON_ERROR);
    exit;
}
function fail(string $message, int $status = 422): never { throw new ApiException($message, $status); }
function input(): array
{
    $raw = file_get_contents('php://input', false, null, 0, 1048577);
    if ($raw === '' || $raw === false) return $_POST;
    if (strlen($raw) > 1048576) fail('Request body is too large.', 413);
    try {
        $root = json_decode($raw, false, 32, JSON_THROW_ON_ERROR);
        $value = json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
    }
    catch (JsonException) { fail('Invalid JSON request.'); }
    if (!is_object($root) || !is_array($value)) fail('A JSON object is required.');
    return $value;
}
function strval_checked(mixed $value, int $max = 255): string
{
    if (!is_string($value) && !is_numeric($value)) fail('Invalid text value.');
    $value = trim((string)$value);
    if (strlen($value) > $max) fail('Text exceeds the allowed length.');
    return $value;
}
function required_text(array $data, string $key, int $max = 255): string
{
    $text = strval_checked($data[$key] ?? '', $max);
    if ($text === '') fail("$key is required.");
    return $text;
}
function money(mixed $value, bool $positive = false): int
{
    if (!is_scalar($value) || !preg_match('/^-?\d{1,12}(?:\.\d{1,2})?$/D', (string)$value)) fail('Amounts must be valid numbers with at most two decimals.');
    $negative = str_starts_with((string)$value, '-');
    $parts = explode('.', ltrim((string)$value, '-'));
    $amount = ((int)$parts[0] * 100) + (int)str_pad($parts[1] ?? '', 2, '0');
    $amount *= $negative ? -1 : 1;
    if ($positive && $amount <= 0) fail('Amount must be greater than zero.');
    return $amount;
}
function major(int|float|string|null $value): float { return (int)$value / 100; }
function currency(mixed $value): string
{
    if (!is_string($value)) fail('Unsupported currency.');
    $value = strtoupper($value);
    if (!in_array($value, SUPPORTED_CURRENCIES, true)) fail('Unsupported currency.');
    return $value;
}
function enum_value(mixed $value, array $allowed, string $field): string
{
    if (!is_string($value) || !in_array($value, $allowed, true)) fail("Invalid $field.");
    return $value;
}
function valid_date(mixed $value, bool $dayOnly = false): string
{
    $value = strval_checked($value, 40);
    if (!preg_match('/^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)?$/D', $value)) fail('A valid ISO date is required.');
    try { $date = new DateTimeImmutable($value, new DateTimeZone(date_default_timezone_get())); } catch (Throwable) { fail('Invalid date.'); }
    $errors = DateTimeImmutable::getLastErrors();
    if ($errors !== false && ($errors['warning_count'] || $errors['error_count'])) fail('Invalid calendar date or time.');
    if ($dayOnly) return $date->format('Y-m-d');
    return $date->setTimezone(new DateTimeZone(date_default_timezone_get()))->format('Y-m-d H:i:s');
}
function valid_month(mixed $value): string
{
    $value = strval_checked($value, 7);
    if (!preg_match('/^\d{4}-(0[1-9]|1[0-2])$/D', $value)) fail('Month must use YYYY-MM.');
    return $value;
}
function valid_color(mixed $value): string
{
    if (!is_string($value)) fail('Color must be a six digit hex code.');
    if (!preg_match('/^#[a-fA-F0-9]{6}$/D', $value)) fail('Color must be a six digit hex code.');
    return $value;
}
function csv_safe(mixed $value): string
{
    $value = (string)$value;
    return preg_match('/^[\s]*[=+@\-]/u', $value) ? "'" . $value : $value;
}
function id_value(mixed $value): int
{
    if (filter_var($value, FILTER_VALIDATE_INT) === false || (int)$value < 1) fail('A valid record ID is required.');
    return (int)$value;
}
