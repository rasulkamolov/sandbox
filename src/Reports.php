<?php
declare(strict_types=1);

/** Read-only, currency-specific operating reports. Money stays in minor units until output. */
final class Reports
{
    public static function build(array $query): array
    {
        Auth::owner();
        $cur = currency($query['currency'] ?? 'USD');
        $from = self::day($query['from'] ?? date('Y-m-01'));
        $to = self::day($query['to'] ?? date('Y-m-d'));
        if ($from > $to) fail('Report start date must be on or before the end date.');
        $first = new DateTimeImmutable($from);
        $days = (int)$first->diff(new DateTimeImmutable($to))->days + 1;
        if ($days > 1830) fail('Choose a report period of five years or less.');
        $accountId = isset($query['account_id']) && $query['account_id'] !== '' ? id_value($query['account_id']) : null;
        if ($accountId !== null && Finance::account($accountId)['currency'] !== $cur) fail('Choose an account in the selected currency.');
        $previousFrom = $first->modify("-$days days")->format('Y-m-d');
        $previousTo = $first->modify('-1 day')->format('Y-m-d');

        // All aggregates describe one snapshot even when another browser records a payment.
        $pdo = Database::connection();
        $ownsTransaction = !$pdo->inTransaction();
        if ($ownsTransaction) $pdo->beginTransaction();
        try {
            $result = self::compile($cur, $from, $to, $previousFrom, $previousTo, $days, $accountId);
            if ($ownsTransaction) $pdo->commit();
            return $result;
        } catch (Throwable $error) {
            if ($ownsTransaction && $pdo->inTransaction()) $pdo->rollBack();
            throw $error;
        }
    }

    private static function day(mixed $value): string
    {
        if (!is_string($value) || !preg_match('/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/D', $value)) fail('Report dates must use YYYY-MM-DD.');
        return valid_date($value, true);
    }

    /** End-exclusive bounds include transactions stored with either dates or timestamps. */
    private static function where(string $cur, string $from, string $to, ?int $accountId, bool $fees = false): array
    {
        $until = (new DateTimeImmutable($to))->modify('+1 day')->format('Y-m-d');
        $sql = 't.currency=? AND t.date>=? AND t.date<?';
        $params = [$cur, $from, $until];
        if ($accountId !== null) {
            $sql .= $fees ? ' AND t.from_account_id=?' : ' AND t.account_id=?';
            $params[] = $accountId;
        }
        return [$sql, $params];
    }

    private static function totals(string $cur, string $from, string $to, int $days, ?int $accountId): array
    {
        [$where, $params] = self::where($cur, $from, $to, $accountId);
        $totals = ['days'=>$days, 'income'=>0, 'expense'=>0, 'transaction_count'=>0, 'fees'=>0];
        foreach (Database::all('SELECT type,SUM(amount) amount,COUNT(*) count FROM transactions t WHERE '.$where.' GROUP BY type', $params) as $row) {
            $totals[$row['type']] = (int)$row['amount'];
            $totals['transaction_count'] += (int)$row['count'];
        }
        [$where, $params] = self::where($cur, $from, $to, $accountId, true);
        $totals['fees'] = (int)Database::scalar('SELECT COALESCE(SUM(fee),0) FROM transfers t WHERE '.$where, $params);
        $totals['expense'] += $totals['fees'];
        $totals['net'] = $totals['income'] - $totals['expense'];
        $totals['savings_rate'] = $totals['income'] > 0 ? round($totals['net'] / $totals['income'] * 100, 1) : null;
        $totals['average_daily_expense'] = round(major($totals['expense']) / $days, 2);
        foreach (['income','expense','net','fees'] as $key) $totals[$key] = major($totals[$key]);
        return $totals;
    }

    private static function compile(string $cur, string $from, string $to, string $previousFrom, string $previousTo, int $days, ?int $accountId): array
    {
        $today = date('Y-m-d');
        $period = self::totals($cur, $from, $to, $days, $accountId);
        $previous = self::totals($cur, $previousFrom, $previousTo, $days, $accountId);
        $changes = [];
        foreach (['income','expense','net'] as $key) {
            $delta = (int)round($period[$key] * 100) - (int)round($previous[$key] * 100);
            $baseline = (int)round($previous[$key] * 100);
            $changes[$key] = ['amount'=>major($delta), 'percent'=>$baseline !== 0 ? round($delta / abs($baseline) * 100, 1) : null];
        }
        [$where, $params] = self::where($cur, $from, $to, $accountId);
        [$feeWhere, $feeParams] = self::where($cur, $from, $to, $accountId, true);

        $categories = [];
        foreach (Database::all("SELECT c.id,c.name,c.icon,c.color,SUM(t.amount) amount,COUNT(*) count FROM transactions t LEFT JOIN categories c ON c.id=t.category_id WHERE $where AND t.type='expense' GROUP BY t.category_id,c.id,c.name,c.icon,c.color", $params) as $row) {
            $categories[] = ['id'=>$row['id'] === null ? null : (int)$row['id'], 'kind'=>$row['id'] === null ? 'uncategorized' : 'category', 'name'=>$row['name'], 'icon'=>$row['icon'] ?? 'tag', 'color'=>$row['color'] ?? '#64748b', 'amount'=>major($row['amount']), 'count'=>(int)$row['count']];
        }
        if ($period['fees'] > 0) {
            $feeCount = (int)Database::scalar("SELECT COUNT(*) FROM transfers t WHERE $feeWhere AND fee>0", $feeParams);
            $categories[] = ['id'=>null, 'kind'=>'transfer_fees', 'name'=>null, 'icon'=>'arrow-left-right', 'color'=>'#f59e0b', 'amount'=>$period['fees'], 'count'=>$feeCount];
        }
        usort($categories, static fn(array $a, array $b): int => $b['amount'] <=> $a['amount'] ?: strcmp($a['name'] ?? $a['kind'], $b['name'] ?? $b['kind']));
        foreach ($categories as &$row) $row['share'] = $period['expense'] > 0 ? round($row['amount'] / $period['expense'] * 100, 2) : 0.0;
        unset($row);

        $daily = [];
        $monthly = [];
        $first = new DateTimeImmutable($from);
        for ($i = 0; $i < $days; $i++) {
            $date = $first->modify("+$i days")->format('Y-m-d');
            $daily[$date] = ['date'=>$date, 'income'=>0, 'expense'=>0, 'net'=>0];
            $month = substr($date, 0, 7);
            $monthly[$month] ??= ['month'=>$month, 'income'=>0, 'expense'=>0, 'net'=>0];
        }
        foreach (Database::all("SELECT substr(t.date,1,10) day,type,SUM(amount) amount FROM transactions t WHERE $where GROUP BY day,type", $params) as $row) {
            if (isset($daily[$row['day']])) $daily[$row['day']][$row['type']] += (int)$row['amount'];
        }
        foreach (Database::all("SELECT substr(t.date,1,10) day,SUM(fee) amount FROM transfers t WHERE $feeWhere GROUP BY day", $feeParams) as $row) {
            if (isset($daily[$row['day']])) $daily[$row['day']]['expense'] += (int)$row['amount'];
        }
        foreach ($daily as &$row) {
            $month = substr($row['date'], 0, 7);
            $monthly[$month]['income'] += $row['income'];
            $monthly[$month]['expense'] += $row['expense'];
            $row['net'] = $row['income'] - $row['expense'];
            foreach (['income','expense','net'] as $key) $row[$key] = major($row[$key]);
        }
        unset($row);
        foreach ($monthly as &$row) {
            $row['net'] = $row['income'] - $row['expense'];
            foreach (['income','expense','net'] as $key) $row[$key] = major($row[$key]);
        }
        unset($row);

        $accountTotals = [];
        foreach (Database::all("SELECT account_id,type,SUM(amount) amount,COUNT(*) count FROM transactions t WHERE $where GROUP BY account_id,type", $params) as $row) {
            $id = (int)$row['account_id'];
            $accountTotals[$id] ??= ['income'=>0, 'expense'=>0, 'transaction_count'=>0];
            $accountTotals[$id][$row['type']] += (int)$row['amount'];
            $accountTotals[$id]['transaction_count'] += (int)$row['count'];
        }
        foreach (Database::all("SELECT from_account_id,SUM(fee) amount FROM transfers t WHERE $feeWhere GROUP BY from_account_id", $feeParams) as $row) {
            $id = (int)$row['from_account_id'];
            $accountTotals[$id] ??= ['income'=>0, 'expense'=>0, 'transaction_count'=>0];
            $accountTotals[$id]['expense'] += (int)$row['amount'];
        }
        $accounts = self::accounts($cur, $accountId, $today);
        $balance = 0;
        foreach ($accounts as &$account) {
            $totals = $accountTotals[$account['id']] ?? ['income'=>0, 'expense'=>0, 'transaction_count'=>0];
            $balance += $account['balance_minor'];
            $account += ['income'=>major($totals['income']), 'expense'=>major($totals['expense']), 'net'=>major($totals['income'] - $totals['expense']), 'transaction_count'=>$totals['transaction_count'], 'current_balance'=>major($account['balance_minor'])];
            unset($account['balance_minor']);
        }
        unset($account);
        $largest = Database::all("SELECT t.id,t.description,c.name category_name,a.name account_name,t.date,t.amount,t.currency FROM transactions t JOIN accounts a ON a.id=t.account_id LEFT JOIN categories c ON c.id=t.category_id WHERE $where AND t.type='expense' ORDER BY t.amount DESC,t.date DESC,t.id DESC LIMIT 8", $params);
        foreach ($largest as &$row) { $row['id'] = (int)$row['id']; $row['amount'] = major($row['amount']); }
        unset($row);

        $budgets = self::budgets($cur, $from, $to, $accountId);
        [$obligations, $debtUpcoming] = self::obligations($cur, $accountId, $today);
        $upcoming = [...$debtUpcoming, ...self::recurring($cur, $accountId, $today)];
        usort($upcoming, static fn(array $a, array $b): int => strcmp($a['date'], $b['date']) ?: strcmp($a['kind'], $b['kind']) ?: $a['id'] <=> $b['id']);
        $expenseMinor = (int)round($period['expense'] * 100);
        $runway = $expenseMinor > 0 ? round(max(0, $balance) * $days / $expenseMinor, 1) : null;
        $liquidity = ['balance'=>major($balance), 'average_daily_expense'=>$period['average_daily_expense'], 'runway_days'=>$runway];
        return [
            'currency'=>$cur, 'from'=>$from, 'to'=>$to, 'previous_from'=>$previousFrom, 'previous_to'=>$previousTo, 'account_id'=>$accountId, 'as_of'=>$today,
            'period'=>$period, 'previous'=>$previous, 'changes'=>$changes, 'categories'=>$categories, 'accounts'=>$accounts,
            'daily'=>array_values($daily), 'monthly'=>array_values($monthly), 'largest_expenses'=>$largest, 'budgets'=>$budgets,
            'obligations'=>$obligations, 'upcoming'=>$upcoming, 'liquidity'=>$liquidity,
            'insights'=>self::insights($period, $previous, $categories, $budgets, $obligations, $liquidity),
        ];
    }

    /** Today's ledger balance includes debt cash movements, never debt principal in profit. */
    private static function accounts(string $cur, ?int $accountId, string $today): array
    {
        $accounts = Database::all('SELECT id,name,type,status,initial_balance balance_minor FROM accounts WHERE currency=?'.($accountId !== null ? ' AND id=?' : '').' ORDER BY status,name,id', $accountId !== null ? [$cur, $accountId] : [$cur]);
        $map = [];
        foreach ($accounts as $account) { $account['id'] = (int)$account['id']; $account['balance_minor'] = (int)$account['balance_minor']; $map[$account['id']] = $account; }
        $until = (new DateTimeImmutable($today))->modify('+1 day')->format('Y-m-d');
        foreach (Database::all("SELECT account_id,SUM(CASE WHEN type='income' THEN amount ELSE -amount END) amount FROM transactions WHERE currency=? AND date<? GROUP BY account_id", [$cur, $until]) as $row) {
            if (isset($map[$row['account_id']])) $map[$row['account_id']]['balance_minor'] += (int)$row['amount'];
        }
        foreach (Database::all('SELECT t.from_account_id,t.to_account_id,t.amount,t.received_amount,t.fee FROM transfers t JOIN accounts a ON a.id=t.to_account_id WHERE t.date<? AND (t.currency=? OR a.currency=?)', [$until, $cur, $cur]) as $row) {
            if (isset($map[$row['from_account_id']])) $map[$row['from_account_id']]['balance_minor'] -= (int)$row['amount'] + (int)$row['fee'];
            if (isset($map[$row['to_account_id']])) $map[$row['to_account_id']]['balance_minor'] += (int)$row['received_amount'];
        }
        foreach (Database::all('SELECT account_id,direction,amount FROM debts WHERE currency=? AND date<? AND account_id IS NOT NULL', [$cur, $until]) as $row) {
            if (isset($map[$row['account_id']])) $map[$row['account_id']]['balance_minor'] += ($row['direction'] === 'borrowing' ? 1 : -1) * (int)$row['amount'];
        }
        foreach (Database::all('SELECT r.account_id,d.direction,r.amount FROM repayments r JOIN debts d ON d.id=r.debt_id WHERE d.currency=? AND r.date<?', [$cur, $until]) as $row) {
            if (isset($map[$row['account_id']])) $map[$row['account_id']]['balance_minor'] += ($row['direction'] === 'lending' ? 1 : -1) * (int)$row['amount'];
        }
        return array_values($map);
    }

    private static function budgets(string $cur, string $from, string $to, ?int $accountId): array
    {
        $rows = Database::all('SELECT b.id,b.category_id,b.month,b.amount,c.name category_name FROM budgets b JOIN categories c ON c.id=b.category_id WHERE b.currency=? AND b.month>=? AND b.month<=? ORDER BY b.month,c.name,b.id', [$cur, substr($from, 0, 7), substr($to, 0, 7)]);
        foreach ($rows as &$row) {
            $params = [$row['category_id'], $cur, $row['month']];
            if ($accountId !== null) $params[] = $accountId;
            $spent = (int)Database::scalar("WITH RECURSIVE tree(id) AS (SELECT id FROM categories WHERE id=? UNION SELECT c.id FROM categories c JOIN tree ON c.parent_id=tree.id) SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='expense' AND category_id IN (SELECT id FROM tree) AND currency=? AND substr(date,1,7)=?".($accountId !== null ? ' AND account_id=?' : ''), $params);
            $cap = (int)$row['amount'];
            $row['id'] = (int)$row['id']; $row['category_id'] = (int)$row['category_id'];
            $row['percentage'] = round($spent / $cap * 100, 1);
            $row['spent'] = major($spent); $row['amount'] = major($cap); $row['remaining'] = major($cap - $spent);
            $row['status'] = $spent >= $cap ? 'danger' : ($spent * 100 >= $cap * 75 ? 'warning' : 'healthy');
            $row['full_month'] = true;
        }
        unset($row);
        return $rows;
    }

    private static function obligations(string $cur, ?int $accountId, string $today): array
    {
        $until = (new DateTimeImmutable($today))->modify('+1 day')->format('Y-m-d');
        $end = (new DateTimeImmutable($today))->modify('+30 days')->format('Y-m-d');
        $params = [$until, $cur, $until];
        if ($accountId !== null) $params[] = $accountId;
        $rows = Database::all('SELECT d.*,a.name account_name,COALESCE((SELECT SUM(r.amount) FROM repayments r WHERE r.debt_id=d.id AND r.date<?),0) paid FROM debts d LEFT JOIN accounts a ON a.id=d.account_id WHERE d.currency=? AND d.date<?'.($accountId !== null ? ' AND d.account_id=?' : ''), $params);
        $totals = array_fill_keys(['payables','receivables','overdue_payables','overdue_receivables','due_next30_payables','due_next30_receivables'], 0);
        $upcoming = [];
        foreach ($rows as $row) {
            $remaining = max(0, (int)$row['amount'] - (int)$row['paid']);
            if ($remaining === 0) continue;
            $key = $row['direction'] === 'borrowing' ? 'payables' : 'receivables';
            $totals[$key] += $remaining;
            if ($row['due_date'] !== null && $row['due_date'] !== '') {
                $due = $row['due_date'];
                if ($due < $today) $totals['overdue_'.$key] += $remaining;
                elseif ($due <= $end) $totals['due_next30_'.$key] += $remaining;
                if ($due <= $end) $upcoming[] = ['kind'=>'debt', 'id'=>(int)$row['id'], 'type'=>$row['direction'] === 'borrowing' ? 'expense' : 'income', 'date'=>$due, 'description'=>$row['counterparty'], 'account_name'=>$row['account_name'], 'amount'=>major($remaining), 'currency'=>$cur, 'overdue'=>$due < $today];
            }
        }
        foreach ($totals as &$amount) $amount = major($amount);
        unset($amount);
        return [$totals, $upcoming];
    }

    private static function recurring(string $cur, ?int $accountId, string $today): array
    {
        $end = (new DateTimeImmutable($today))->modify('+30 days')->format('Y-m-d');
        $rows = Database::all("SELECT r.*,a.name account_name FROM recurring r JOIN accounts a ON a.id=r.account_id WHERE r.enabled=1 AND a.status='active' AND a.currency=?".($accountId !== null ? ' AND r.account_id=?' : ''), $accountId !== null ? [$cur, $accountId] : [$cur]);
        $posted = [];
        foreach (Database::all('SELECT recurring_id,occurrence_date FROM transactions WHERE recurring_id IS NOT NULL AND occurrence_date<=?', [$end]) as $row) $posted[$row['recurring_id']][$row['occurrence_date']] = true;
        $upcoming = [];
        foreach ($rows as $row) {
            $next = $row['next_date'];
            $oldestOverdueIncluded = false;
            // A stale schedule contributes its oldest outstanding occurrence once; do not disguise it as due today.
            while ($next <= $end) {
                if (!isset($posted[$row['id']][$next]) && ($next >= $today || !$oldestOverdueIncluded)) {
                    $upcoming[] = ['kind'=>'recurring', 'id'=>(int)$row['id'], 'type'=>$row['type'], 'date'=>$next, 'description'=>$row['description'], 'account_name'=>$row['account_name'], 'amount'=>major($row['amount']), 'currency'=>$cur, 'overdue'=>$next < $today];
                    if ($next < $today) $oldestOverdueIncluded = true;
                }
                // Jump long daily/weekly backlogs while preserving the next real recurrence.
                if ($next < $today && in_array($row['frequency'], ['daily','weekly'], true)) {
                    $step = $row['frequency'] === 'daily' ? 1 : 7;
                    $gap = (int)(new DateTimeImmutable($next))->diff(new DateTimeImmutable($today))->days;
                    $jump = max(1, intdiv($gap + $step - 1, $step)) * $step;
                    $next = (new DateTimeImmutable($next))->modify("+$jump days")->format('Y-m-d');
                } else {
                    $following = Finance::nextOccurrence($row, $next);
                    if ($following <= $next) break;
                    $next = $following;
                }
            }
        }
        return $upcoming;
    }

    private static function insights(array $period, array $previous, array $categories, array $budgets, array $obligations, array $liquidity): array
    {
        $insights = [];
        if ($period['transaction_count'] === 0 && $period['fees'] === 0.0) $insights[] = ['code'=>'no_activity', 'severity'=>'info', 'values'=>[]];
        if ($obligations['overdue_payables'] > 0) $insights[] = ['code'=>'overdue_debts', 'severity'=>'danger', 'values'=>['amount'=>$obligations['overdue_payables']]];
        $exceeded = array_values(array_filter($budgets, static fn(array $budget): bool => $budget['status'] === 'danger'));
        if ($exceeded) $insights[] = ['code'=>'budget_exceeded', 'severity'=>'warning', 'values'=>['count'=>count($exceeded), 'amount'=>round(array_sum(array_map(static fn(array $budget): float => max(0, $budget['spent'] - $budget['amount']), $exceeded)), 2)]];
        if ($period['income'] === 0.0 && $period['expense'] > 0) $insights[] = ['code'=>'no_income', 'severity'=>'warning', 'values'=>[]];
        if ($liquidity['runway_days'] !== null && $liquidity['runway_days'] < 30) $insights[] = ['code'=>'low_runway', 'severity'=>'warning', 'values'=>['days'=>$liquidity['runway_days']]];
        if ($previous['expense'] > 0) {
            $percent = round(($period['expense'] - $previous['expense']) / $previous['expense'] * 100, 1);
            if (abs($percent) >= 10) $insights[] = ['code'=>$percent > 0 ? 'spending_increased' : 'spending_decreased', 'severity'=>$percent > 0 ? 'warning' : 'success', 'values'=>['percent'=>abs($percent), 'amount'=>round(abs($period['expense'] - $previous['expense']), 2)]];
        }
        if ($period['net'] !== 0.0) $insights[] = ['code'=>$period['net'] > 0 ? 'savings_positive' : 'savings_negative', 'severity'=>$period['net'] > 0 ? 'success' : 'warning', 'values'=>['amount'=>abs($period['net']), 'rate'=>$period['savings_rate']]];
        if ($categories) $insights[] = ['code'=>'biggest_category', 'severity'=>'info', 'values'=>array_intersect_key($categories[0], array_flip(['name','kind','share','amount']))];
        return $insights;
    }

    /** Flat rows keep the report useful in spreadsheet software; the endpoint handles CSV escaping. */
    public static function export(array $query): array
    {
        $report = self::build($query);
        $locale = in_array($_SESSION['locale'] ?? 'en', SUPPORTED_LOCALES, true) ? $_SESSION['locale'] : 'en';
        $translations = require APP_ROOT.'/lang/'.$locale.'.php';
        $fallback = require APP_ROOT.'/lang/en.php';
        $t = static fn(string $key): string => $translations[$key] ?? $fallback[$key] ?? $key;
        $headers = array_map($t, ['report_csv_section','report_csv_date','report_csv_name','report_csv_income','report_csv_expense','report_csv_net','report_csv_amount','report_csv_currency','report_csv_percentage','report_csv_count']);
        $rows = [];
        $cur = $report['currency'];
        foreach (['period','previous'] as $section) {
            $value = $report[$section];
            $dates = $section === 'period' ? $report['from'].' / '.$report['to'] : $report['previous_from'].' / '.$report['previous_to'];
            $rows[] = [$t('report_csv_'.$section), $dates, $t('report_csv_'.$section), $value['income'], $value['expense'], $value['net'], '', $cur, $value['savings_rate'] ?? '', $value['transaction_count']];
        }
        foreach ($report['categories'] as $row) $rows[] = [$t('report_csv_category'), '', $row['name'] ?? $t($row['kind'] === 'transfer_fees' ? 'transfer_fee' : 'uncategorized'), '', '', '', $row['amount'], $cur, $row['share'], $row['count']];
        foreach ($report['accounts'] as $row) {
            $rows[] = [$t('report_csv_account'), $report['from'].' / '.$report['to'], $row['name'], $row['income'], $row['expense'], $row['net'], '', $cur, '', $row['transaction_count']];
            $rows[] = [$t('report_csv_balance'), $report['as_of'], $row['name'], '', '', '', $row['current_balance'], $cur, '', ''];
        }
        foreach (['daily'=>'date','monthly'=>'month'] as $section=>$dateKey) foreach ($report[$section] as $row) $rows[] = [$t('report_csv_'.$section), $row[$dateKey], '', $row['income'], $row['expense'], $row['net'], '', $cur, '', ''];
        foreach ($report['largest_expenses'] as $row) $rows[] = [$t('report_csv_largest'), $row['date'], $row['description'] ?: ($row['category_name'] ?? $t('uncategorized')), '', '', '', $row['amount'], $cur, '', ''];
        foreach ($report['budgets'] as $row) {
            $rows[] = [$t('report_csv_budget_limit'), $row['month'], $row['category_name'], '', '', '', $row['amount'], $cur, '', ''];
            $rows[] = [$t('report_csv_budget_spent'), $row['month'], $row['category_name'], '', '', '', $row['spent'], $cur, $row['percentage'], ''];
        }
        foreach ($report['obligations'] as $key=>$amount) $rows[] = [$t('report_csv_obligation'), $report['as_of'], $t('report_csv_'.$key), '', '', '', $amount, $cur, '', ''];
        foreach ($report['upcoming'] as $row) $rows[] = [$t('report_csv_upcoming'), $row['date'], $row['description'], $row['type'] === 'income' ? $row['amount'] : '', $row['type'] === 'expense' ? $row['amount'] : '', '', $row['amount'], $cur, '', ''];
        return ['headers'=>$headers, 'rows'=>$rows];
    }
}
