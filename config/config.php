<?php
declare(strict_types=1);

const APP_NAME = 'Vela';
const APP_ROOT = __DIR__ . '/..';
define('DATABASE_PATH', getenv('FINANCE_DB_PATH') ?: APP_ROOT . '/database/finance.db');
const SUPPORTED_CURRENCIES = ['UZS', 'USD', 'EUR', 'RUB'];
const SUPPORTED_LOCALES = ['en', 'uz', 'ru'];
const SESSION_IDLE_SECONDS = 1800;
date_default_timezone_set('Asia/Samarkand');
