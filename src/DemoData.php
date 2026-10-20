<?php
declare(strict_types=1);

/** Owner-controlled financial cleanup. Authentication and history are retained. */
final class DemoData
{
    private const TABLES = ['accounts','categories','tags','transactions','transfers','budgets','debts','repayments','recurring'];

    public static function status(): array
    {
        Auth::owner();
        $byResource = [];
        $total = 0;
        $sample = 0;
        foreach (self::TABLES as $table) {
            $counts = Database::one('SELECT COUNT(*) total, COALESCE(SUM(is_demo),0) sample FROM ' . $table);
            $byResource[$table] = ['total'=>(int)$counts['total'], 'sample'=>(int)$counts['sample']];
            $total += $byResource[$table]['total'];
            $sample += $byResource[$table]['sample'];
        }
        $lastSeed = (int)Database::scalar("SELECT COALESCE(MAX(id),0) FROM audit_logs WHERE action='seed_demo'");
        $lastCleanup = (int)Database::scalar("SELECT COALESCE(MAX(id),0) FROM audit_logs WHERE action IN ('clear_sample_data','reset_finances')");
        return [
            'sample_records'=>$sample,
            'financial_records'=>$total,
            'by_resource'=>$byResource,
            'can_remove_samples'=>$sample > 0,
            // Old installations have no trustworthy per-record demo markers.
            // Never guess which of their existing records should be deleted.
            'legacy_sample_data_possible'=>$sample === 0 && $total > 0 && $lastSeed > $lastCleanup,
        ];
    }

    private static function authorize(array $data, string $confirmation): void
    {
        $owner = Auth::owner();
        if (!is_string($data['confirmation'] ?? null) || !hash_equals($confirmation, $data['confirmation'])) {
            fail('Type the exact confirmation phrase to continue.');
        }
        $password = $data['current_password'] ?? null;
        $hash = Database::scalar('SELECT password_hash FROM users WHERE id=?', [$owner['id']]);
        if (!is_string($password) || $password === '' || strlen($password) > 72 || !is_string($hash) || !password_verify($password, $hash)) {
            fail('Your current password is incorrect.');
        }
    }

    /** Remove only explicitly marked examples; preserve all actual user records. */
    public static function clear(array $data): array
    {
        return Database::atomic(function () use ($data): array {
            self::authorize($data, 'REMOVE SAMPLE DATA');
            $before = self::status();
            $deleted = array_fill_keys(self::TABLES, 0);

            // A real repayment makes the entire debt meaningful. Keep its original
            // principal and all repayments so clearing examples cannot increase or
            // decrease a real person's outstanding debt.
            Database::query('UPDATE debts SET is_demo=0 WHERE is_demo=1 AND EXISTS (SELECT 1 FROM repayments r WHERE r.debt_id=debts.id AND r.is_demo=0)');
            Database::query('UPDATE repayments SET is_demo=0 WHERE is_demo=1 AND EXISTS (SELECT 1 FROM debts d WHERE d.id=repayments.debt_id AND d.is_demo=0)');

            foreach (['transactions','transfers','budgets','repayments','debts'] as $table) {
                $deleted[$table] = Database::query('DELETE FROM ' . $table . ' WHERE is_demo=1')->rowCount();
            }

            // Keep a schedule referenced by a genuine, possibly user-edited entry.
            Database::query('UPDATE recurring SET is_demo=0 WHERE is_demo=1 AND EXISTS (SELECT 1 FROM transactions t WHERE t.recurring_id=recurring.id)');
            $deleted['recurring'] = Database::query('DELETE FROM recurring WHERE is_demo=1')->rowCount();

            // Only remove sample storage locations after their sample movements
            // are gone. An account now used by real records remains unchanged.
            $deleted['accounts'] = Database::query(<<<'SQL'
DELETE FROM accounts WHERE is_demo=1
 AND NOT EXISTS (SELECT 1 FROM transactions WHERE account_id=accounts.id)
 AND NOT EXISTS (SELECT 1 FROM transfers WHERE from_account_id=accounts.id OR to_account_id=accounts.id)
 AND NOT EXISTS (SELECT 1 FROM debts WHERE account_id=accounts.id)
 AND NOT EXISTS (SELECT 1 FROM repayments WHERE account_id=accounts.id)
 AND NOT EXISTS (SELECT 1 FROM recurring WHERE account_id=accounts.id)
SQL)->rowCount();
            Database::query('UPDATE accounts SET is_demo=0 WHERE is_demo=1');

            // Delete unused leaves first; retain every ancestor of a real child
            // category and every category referenced by an actual financial row.
            do {
                $removed = Database::query(<<<'SQL'
DELETE FROM categories WHERE is_demo=1
 AND NOT EXISTS (SELECT 1 FROM categories child WHERE child.parent_id=categories.id)
 AND NOT EXISTS (SELECT 1 FROM transactions WHERE category_id=categories.id)
 AND NOT EXISTS (SELECT 1 FROM budgets WHERE category_id=categories.id)
 AND NOT EXISTS (SELECT 1 FROM recurring WHERE category_id=categories.id)
SQL)->rowCount();
                $deleted['categories'] += $removed;
            } while ($removed > 0);
            Database::query('UPDATE categories SET is_demo=0 WHERE is_demo=1');

            $deleted['tags'] = Database::query('DELETE FROM tags WHERE is_demo=1 AND NOT EXISTS (SELECT 1 FROM transaction_tags WHERE tag_id=tags.id)')->rowCount();
            Database::query('UPDATE tags SET is_demo=0 WHERE is_demo=1');

            $preserved = [];
            foreach (self::TABLES as $table) $preserved[$table] = $before['by_resource'][$table]['sample'] - $deleted[$table];
            Database::audit($before['sample_records'] > 0 ? 'clear_sample_data' : 'clear_sample_data_noop', 'database');
            return [
                'deleted_records'=>array_sum($deleted),
                'preserved_records'=>array_sum($preserved),
                'deleted'=>$deleted,
                'preserved'=>$preserved,
                'status'=>self::status(),
            ];
        });
    }

    /** Explicitly start finances over, including unmarked legacy sample data. */
    public static function reset(array $data): array
    {
        return Database::atomic(function () use ($data): array {
            self::authorize($data, 'RESET FINANCES');
            $deleted = [];
            // Junction rows are intentionally excluded from the user-facing count.
            Database::query('DELETE FROM transaction_tags');
            foreach (['transactions','transfers','repayments','budgets','debts','recurring','accounts','tags'] as $table) {
                $deleted[$table] = Database::query('DELETE FROM ' . $table)->rowCount();
            }
            // Clearing all categories also clears their parent links. This avoids
            // SQLite's immediate self-reference restriction and handles any depth.
            Database::query('UPDATE categories SET parent_id=NULL WHERE parent_id IS NOT NULL');
            $deleted['categories'] = Database::query('DELETE FROM categories')->rowCount();
            Database::audit('reset_finances', 'database');
            return [
                'deleted_records'=>array_sum($deleted),
                'preserved_records'=>0,
                'deleted'=>$deleted,
                'preserved'=>array_fill_keys(self::TABLES, 0),
                'status'=>self::status(),
            ];
        });
    }
}
