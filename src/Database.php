<?php
declare(strict_types=1);

final class Database
{
    private static ?PDO $connection = null;
    public static function connection(): PDO
    {
        if (self::$connection) return self::$connection;
        $dir = dirname(DATABASE_PATH);
        if (!is_dir($dir) && !mkdir($dir, 0700, true) && !is_dir($dir)) throw new RuntimeException('Unable to create database directory.');
        $pdo = new PDO('sqlite:' . DATABASE_PATH, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC, PDO::ATTR_EMULATE_PREPARES => false]);
        $pdo->exec('PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 10000;');
        self::$connection = $pdo;
        self::schema();
        if (file_exists(DATABASE_PATH)) @chmod(DATABASE_PATH, 0600);
        return $pdo;
    }
    public static function query(string $sql, array $params = []): PDOStatement
    {
        $stmt = self::connection()->prepare($sql); $stmt->execute($params); return $stmt;
    }
    public static function all(string $sql, array $params = []): array { return self::query($sql, $params)->fetchAll(); }
    public static function one(string $sql, array $params = []): ?array { return self::query($sql, $params)->fetch() ?: null; }
    public static function scalar(string $sql, array $params = []): mixed { return self::query($sql, $params)->fetchColumn(); }
    public static function insert(string $table, array $data): int
    {
        $columns = array_keys($data);
        self::query('INSERT INTO ' . $table . ' (' . implode(',', $columns) . ') VALUES (' . implode(',', array_fill(0, count($columns), '?')) . ')', array_values($data));
        return (int)self::connection()->lastInsertId();
    }
    public static function update(string $table, int $id, array $data): void
    {
        self::query('UPDATE ' . $table . ' SET ' . implode(',', array_map(static fn($key) => "$key = ?", array_keys($data))) . ' WHERE id = ?', [...array_values($data), $id]);
    }
    public static function atomic(callable $callback): mixed
    {
        $pdo = self::connection(); $pdo->exec('BEGIN IMMEDIATE');
        try { $result = $callback(); $pdo->exec('COMMIT'); return $result; }
        catch (Throwable $e) { $pdo->exec('ROLLBACK'); throw $e; }
    }
    public static function audit(string $action, string $entity, ?int $id = null): void
    {
        self::insert('audit_logs', ['user_id' => $_SESSION['user_id'] ?? null, 'action' => $action, 'entity' => $entity, 'entity_id' => $id, 'ip' => substr($_SERVER['REMOTE_ADDR'] ?? 'local', 0, 64), 'created_at' => date('Y-m-d H:i:s')]);
    }
    private static function schema(): void
    {
        self::$connection->exec(<<<'SQL'
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL COLLATE NOCASE UNIQUE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','assistant')),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)), auth_version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS login_attempts (id INTEGER PRIMARY KEY, attempt_key TEXT NOT NULL, attempted_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS login_attempt_key ON login_attempts(attempt_key,attempted_at);
CREATE TABLE IF NOT EXISTS accounts (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL CHECK(type IN ('bank','card','cash','savings','digital')),
 currency TEXT NOT NULL CHECK(currency IN ('UZS','USD','EUR','RUB')), initial_balance INTEGER NOT NULL DEFAULT 0,
 icon TEXT NOT NULL DEFAULT 'wallet', color TEXT NOT NULL DEFAULT '#10b981', status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
 details TEXT NOT NULL DEFAULT '', target_amount INTEGER NOT NULL DEFAULT 0, is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN(0,1)), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS categories (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL CHECK(type IN ('income','expense')),
 parent_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT, icon TEXT NOT NULL DEFAULT 'tag', color TEXT NOT NULL DEFAULT '#10b981', is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN(0,1))
);
CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE, color TEXT NOT NULL DEFAULT '#06b6d4', is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN(0,1)));
CREATE TABLE IF NOT EXISTS recurring (
 id INTEGER PRIMARY KEY, type TEXT NOT NULL CHECK(type IN ('income','expense')), amount INTEGER NOT NULL CHECK(amount>0),
 account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
 category_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT,
 description TEXT NOT NULL DEFAULT '', frequency TEXT NOT NULL CHECK(frequency IN ('daily','weekly','monthly','annual')),
 next_date TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN(0,1)), anchor_day INTEGER NOT NULL DEFAULT 1, anchor_month INTEGER NOT NULL DEFAULT 1,
 created_by INTEGER REFERENCES users(id) ON DELETE RESTRICT, is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN(0,1))
);
CREATE TABLE IF NOT EXISTS transactions (
 id INTEGER PRIMARY KEY, type TEXT NOT NULL CHECK(type IN ('income','expense')), amount INTEGER NOT NULL CHECK(amount>0),
 currency TEXT NOT NULL CHECK(currency IN ('UZS','USD','EUR','RUB')), account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
 category_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT, date TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', receipt TEXT NOT NULL DEFAULT '', recurring_id INTEGER REFERENCES recurring(id) ON DELETE SET NULL,
 occurrence_date TEXT, created_by INTEGER REFERENCES users(id) ON DELETE RESTRICT, is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN(0,1)), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(recurring_id,occurrence_date)
);
CREATE INDEX IF NOT EXISTS transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS transactions_account ON transactions(account_id,date);
CREATE TABLE IF NOT EXISTS transaction_tags (transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE, tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE, PRIMARY KEY(transaction_id,tag_id));
CREATE TABLE IF NOT EXISTS transfers (
 id INTEGER PRIMARY KEY, from_account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
 to_account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT, amount INTEGER NOT NULL CHECK(amount>0), fee INTEGER NOT NULL DEFAULT 0 CHECK(fee>=0),
 currency TEXT NOT NULL CHECK(currency IN ('UZS','USD','EUR','RUB')), received_amount INTEGER NOT NULL CHECK(received_amount>0), date TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 created_by INTEGER REFERENCES users(id) ON DELETE RESTRICT, is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN(0,1)), CHECK(from_account_id<>to_account_id)
);
CREATE TABLE IF NOT EXISTS budgets (
 id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT, amount INTEGER NOT NULL CHECK(amount>0),
 currency TEXT NOT NULL CHECK(currency IN ('UZS','USD','EUR','RUB')), month TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN(0,1)), UNIQUE(category_id,currency,month)
);
CREATE TABLE IF NOT EXISTS debts (
 id INTEGER PRIMARY KEY, direction TEXT NOT NULL CHECK(direction IN ('borrowing','lending')), counterparty TEXT NOT NULL, contact TEXT NOT NULL DEFAULT '',
 amount INTEGER NOT NULL CHECK(amount>0), currency TEXT NOT NULL CHECK(currency IN ('UZS','USD','EUR','RUB')),
 account_id INTEGER REFERENCES accounts(id) ON DELETE RESTRICT, date TEXT NOT NULL, due_date TEXT,
 description TEXT NOT NULL DEFAULT '', created_by INTEGER REFERENCES users(id) ON DELETE RESTRICT, is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN(0,1))
);
CREATE TABLE IF NOT EXISTS repayments (
 id INTEGER PRIMARY KEY, debt_id INTEGER NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
 account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT, amount INTEGER NOT NULL CHECK(amount>0),
 date TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', created_by INTEGER REFERENCES users(id) ON DELETE RESTRICT, is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN(0,1))
);
CREATE TABLE IF NOT EXISTS audit_logs (
 id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE RESTRICT, action TEXT NOT NULL,
 entity TEXT NOT NULL, entity_id INTEGER, ip TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_logs BEGIN SELECT RAISE(ABORT,'Audit logs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_logs BEGIN SELECT RAISE(ABORT,'Audit logs are immutable'); END;
SQL);
        // Migrate existing file-manager installations in place. Acquiring the write
        // lock before inspecting columns makes concurrent first requests safe.
        self::$connection->exec('BEGIN IMMEDIATE');
        try {
            $columns = array_column(self::$connection->query('PRAGMA table_info(transfers)')->fetchAll(), 'name');
            if (!in_array('received_amount', $columns, true)) {
                self::$connection->exec('ALTER TABLE transfers ADD COLUMN received_amount INTEGER NOT NULL DEFAULT 0; UPDATE transfers SET received_amount=amount WHERE received_amount=0;');
            }
            foreach (['accounts','categories','tags','transactions','transfers','budgets','debts','repayments','recurring'] as $table) {
                $columns = array_column(self::$connection->query('PRAGMA table_info(' . $table . ')')->fetchAll(), 'name');
                if (!in_array('is_demo', $columns, true)) {
                    // Existing rows are deliberately unmarked: their origin cannot
                    // safely be inferred from names, dates, balances, or amounts.
                    self::$connection->exec('ALTER TABLE ' . $table . ' ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN(0,1))');
                }
            }
            self::$connection->exec('COMMIT');
        } catch (Throwable $e) {
            self::$connection->exec('ROLLBACK');
            throw $e;
        }
    }
}
