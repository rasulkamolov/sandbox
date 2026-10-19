<?php
declare(strict_types=1);
// Local scheduler entry point. It is deliberately outside the public document root.
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require_once __DIR__ . '/../config/config.php';
require_once APP_ROOT . '/src/Helpers.php';
require_once APP_ROOT . '/src/Database.php';
require_once APP_ROOT . '/src/Auth.php';
require_once APP_ROOT . '/src/Finance.php';
try {
    $owner = Database::one("SELECT id,auth_version FROM users WHERE role='owner' AND active=1 ORDER BY id LIMIT 1");
    if (!$owner) throw new RuntimeException('Create an active owner account before processing recurring entries.');
    // A local process with database access already holds workspace authority.
    // Use the owner identity for attribution without creating a web session.
    $_SESSION = ['user_id' => (int)$owner['id'], 'auth_version' => (int)$owner['auth_version']];
    $result = Finance::processRecurring();
    printf("%s: processed %d recurring entries.\n", date(DATE_ATOM), $result['processed']);
} catch (Throwable $e) {
    fwrite(STDERR, 'Recurring processing failed: ' . $e->getMessage() . "\n");
    exit(1);
}
