<?php
declare(strict_types=1);
require_once __DIR__ . '/config.php';
require_once APP_ROOT . '/src/Database.php';
return Database::connection();
