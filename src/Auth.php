<?php
declare(strict_types=1);

final class Auth
{
    public static function start(): void
    {
        ini_set('session.use_strict_mode', '1');
        ini_set('session.use_only_cookies', '1');
        if ($sessionPath = getenv('FINANCE_SESSION_PATH')) {
            if (!is_dir($sessionPath)) mkdir($sessionPath, 0700, true);
            session_save_path($sessionPath);
        }
        session_name('vela_session');
        session_set_cookie_params(['lifetime' => 0, 'path' => '/', 'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off', 'httponly' => true, 'samesite' => 'Lax']);
        session_start();
        if (isset($_SESSION['last_activity']) && time() - $_SESSION['last_activity'] > SESSION_IDLE_SECONDS) self::clear();
        $_SESSION['last_activity'] = time();
        $_SESSION['csrf'] ??= bin2hex(random_bytes(32));
        $_SESSION['locale'] ??= 'en';
    }
    public static function user(): ?array
    {
        if (empty($_SESSION['user_id'])) return null;
        $user = Database::one('SELECT id,name,email,role,active,auth_version FROM users WHERE id=?', [$_SESSION['user_id']]);
        if (!$user || !$user['active'] || $user['auth_version'] !== ($_SESSION['auth_version'] ?? null)) { self::clear(); return null; }
        unset($user['active'], $user['auth_version']); return $user;
    }
    public static function requireUser(): array { return self::user() ?? fail('Please sign in to continue.', 401); }
    public static function owner(): array
    {
        $user = self::requireUser();
        if ($user['role'] !== 'owner') fail('Owner access is required.', 403);
        return $user;
    }
    public static function csrf(): void
    {
        $token = $_SERVER['HTTP_X_CSRF_TOKEN'] ?? $_POST['_csrf'] ?? '';
        if (!is_string($token) || !hash_equals($_SESSION['csrf'], $token)) fail('Your security token has expired. Refresh and try again.', 419);
        $origin = $_SERVER['HTTP_ORIGIN'] ?? null;
        if ($origin) {
            $originHost = parse_url($origin, PHP_URL_HOST);
            $host = parse_url('http://' . ($_SERVER['HTTP_HOST'] ?? ''), PHP_URL_HOST);
            if (!is_string($host)) fail('Invalid request host.', 403);
            if (!is_string($originHost) || !hash_equals(strtolower($host), strtolower($originHost))) fail('Invalid request origin.', 403);
        }
    }
    public static function validatePassword(mixed $password): string
    {
        if (!is_string($password) || strlen($password) < 12 || strlen($password) > 72) fail('Use a password between 12 and 72 bytes.');
        return $password;
    }
    public static function email(mixed $email): string
    {
        $email = strtolower(strval_checked($email, 254));
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) fail('Enter a valid email address.');
        return $email;
    }
    public static function signIn(array $user): void
    {
        session_regenerate_id(true); $_SESSION['user_id'] = (int)$user['id']; $_SESSION['auth_version'] = (int)$user['auth_version'];
        $_SESSION['csrf'] = bin2hex(random_bytes(32)); $_SESSION['last_activity'] = time();
    }
    public static function login(array $data): array
    {
        $email = self::email($data['email'] ?? '');
        $key = hash('sha256', ($_SERVER['REMOTE_ADDR'] ?? 'local') . '|' . $email);
        $ipKey = hash('sha256', 'ip|' . ($_SERVER['REMOTE_ADDR'] ?? 'local'));
        Database::query('DELETE FROM login_attempts WHERE attempted_at < ?', [time()-3600]);
        if ((int)Database::scalar('SELECT COUNT(*) FROM login_attempts WHERE attempt_key IN (?,?) AND attempted_at > ?', [$key, $ipKey, time()-900]) >= 20) fail('Too many attempts. Please try again in 15 minutes.', 429);
        $user = Database::one('SELECT * FROM users WHERE email=? COLLATE NOCASE', [$email]);
        $password = is_string($data['password'] ?? null) ? $data['password'] : '';
        $hash = $user['password_hash'] ?? '$2y$12$E6pDq1mMQQgU1KPF7pRtMOW4A7rVp9aW2JatpM1c2CwQPBgt0zACy';
        $valid = password_verify($password, $hash);
        if (!$user || !$valid || !$user['active']) {
            Database::insert('login_attempts', ['attempt_key'=>$key,'attempted_at'=>time()]);
            Database::insert('login_attempts', ['attempt_key'=>$ipKey,'attempted_at'=>time()]);
            fail('Email or password is incorrect.', 401);
        }
        Database::query('DELETE FROM login_attempts WHERE attempt_key=?', [$key]);
        self::signIn($user); Database::audit('login', 'users', (int)$user['id']);
        return self::session();
    }
    public static function clear(): void
    {
        $locale = $_SESSION['locale'] ?? 'en';
        $_SESSION = ['locale'=>$locale, 'csrf'=>bin2hex(random_bytes(32)), 'last_activity'=>time()];
        session_regenerate_id(true);
    }
    public static function session(): array
    {
        return ['user'=>self::user(), 'csrf'=>$_SESSION['csrf'], 'locale'=>$_SESSION['locale'], 'needs_setup'=>(int)Database::scalar('SELECT COUNT(*) FROM users')===0, 'currencies'=>SUPPORTED_CURRENCIES];
    }
}
