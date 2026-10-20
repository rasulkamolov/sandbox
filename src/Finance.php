<?php
declare(strict_types=1);

final class Finance
{
    private const RESOURCES = ['accounts','transactions','transfers','budgets','debts','categories','tags','recurring','repayments','users','audit'];
    private const OWNER_RESOURCES = ['transfers','budgets','debts','repayments','users','audit'];

    public static function bootstrap(): array
    {
        $user = Auth::requireUser();
        $result = ['user'=>$user,'accounts'=>self::listing('accounts'),'categories'=>self::listing('categories'),'tags'=>self::listing('tags'),'transactions'=>self::listing('transactions'),'recurring'=>self::listing('recurring')];
        if ($user['role'] === 'owner') {
            foreach (['transfers','budgets','debts','users','audit'] as $resource) $result[$resource] = self::listing($resource);
            $result['summary'] = self::summary(); $result['analytics'] = self::analytics(currency($_GET['currency'] ?? 'USD'));
        } else {
            foreach (['transfers','budgets','debts'] as $resource) $result[$resource] = [];
        }
        return $result;
    }
    public static function account(int $id, bool $active = false): array
    {
        $row = Database::one('SELECT * FROM accounts WHERE id=?', [$id]);
        if (!$row) fail('Account not found.',404);
        if ($active && $row['status'] !== 'active') fail('Choose an active account.');
        return $row;
    }
    private static function category(?int $id, ?string $type = null): ?array
    {
        if (!$id) return null;
        $row = Database::one('SELECT * FROM categories WHERE id=?', [$id]);
        if (!$row || ($type !== null && $row['type'] !== $type)) fail('Choose a category matching the transaction type.');
        return $row;
    }
    public static function balances(): array
    {
        $balances = [];
        foreach (Database::all('SELECT id,initial_balance FROM accounts') as $a) $balances[$a['id']] = (int)$a['initial_balance'];
        foreach (Database::all("SELECT account_id,SUM(CASE WHEN type='income' THEN amount ELSE -amount END) amount FROM transactions GROUP BY account_id") as $r) $balances[$r['account_id']] += (int)$r['amount'];
        foreach (Database::all('SELECT * FROM transfers') as $r) { $balances[$r['from_account_id']] -= (int)$r['amount']+(int)$r['fee']; $balances[$r['to_account_id']] += (int)$r['received_amount']; }
        foreach (Database::all('SELECT * FROM debts WHERE account_id IS NOT NULL') as $r) $balances[$r['account_id']] += ($r['direction']==='borrowing'?1:-1)*(int)$r['amount'];
        foreach (Database::all('SELECT r.*,d.direction FROM repayments r JOIN debts d ON d.id=r.debt_id') as $r) $balances[$r['account_id']] += ($r['direction']==='lending'?1:-1)*(int)$r['amount'];
        return $balances;
    }
    private static function filters(string $alias = 't', bool $category = false): array
    {
        $where = []; $params = [];
        if (isset($_GET['from']) && $_GET['from'] !== '') { $where[]="$alias.date >= ?"; $params[]=valid_date($_GET['from'],true).' 00:00:00'; }
        if (isset($_GET['to']) && $_GET['to'] !== '') { $where[]="$alias.date <= ?"; $params[]=valid_date($_GET['to'],true).' 23:59:59'; }
        if (isset($_GET['account_id']) && $_GET['account_id'] !== '') { $where[]="$alias.account_id=?"; $params[]=id_value($_GET['account_id']); }
        if ($category && isset($_GET['category_id']) && $_GET['category_id'] !== '') { $where[]="$alias.category_id=?"; $params[]=id_value($_GET['category_id']); }
        if (!empty($_GET['search'])) { $where[]="$alias.description LIKE ?"; $params[]='%'.strval_checked($_GET['search']).'%'; }
        return [$where ? ' WHERE '.implode(' AND ',$where) : '', $params];
    }
    public static function listing(string $resource): array
    {
        $user = Auth::requireUser();
        if (!in_array($resource,self::RESOURCES,true)) fail('Unknown resource.',404);
        if (in_array($resource,self::OWNER_RESOURCES,true)) Auth::owner();
        if ($resource === 'accounts') {
            $accounts = Database::all('SELECT * FROM accounts ORDER BY status,name');
            $balances = $user['role']==='owner' ? self::balances() : [];
            $out=[];
            foreach ($accounts as $a) {
                if (!empty($_GET['search']) && stripos($a['name'],(string)$_GET['search'])===false) continue;
                if (!empty($_GET['status']) && $a['status']!==$_GET['status']) continue;
                if ($user['role'] !== 'owner') { $out[]=array_intersect_key($a,array_flip(['id','name','type','currency'])); continue; }
                $a['initial_balance']=major($a['initial_balance']); $a['target_amount']=major($a['target_amount']); $a['current_balance']=major($balances[$a['id']]??0); $out[]=$a;
            }
            return $out;
        }
        if ($resource === 'transactions') {
            [$where,$params]=self::filters('t',true);
            if (!empty($_GET['type'])) { $where.=($where?' AND ':' WHERE ').'t.type=?'; $params[]=enum_value($_GET['type'],['income','expense'],'type'); }
            $rows=Database::all('SELECT t.*,a.name account_name,c.name category_name,c.icon category_icon,c.color category_color FROM transactions t JOIN accounts a ON a.id=t.account_id LEFT JOIN categories c ON c.id=t.category_id'.$where.' ORDER BY t.date DESC,t.id DESC',$params);
            foreach ($rows as &$r) { $r['amount']=major($r['amount']); $r['tags']=array_column(Database::all('SELECT g.name FROM tags g JOIN transaction_tags tt ON g.id=tt.tag_id WHERE tt.transaction_id=?',[$r['id']]),'name'); }
            return $rows;
        }
        if ($resource === 'transfers') {
            $where=[];$params=[];
            if (!empty($_GET['account_id'])) { $where[]='(t.from_account_id=? OR t.to_account_id=?)'; $id=id_value($_GET['account_id']); $params=[$id,$id]; }
            if (!empty($_GET['from'])) { $where[]='t.date>=?';$params[]=valid_date($_GET['from'],true).' 00:00:00'; }
            if (!empty($_GET['to'])) { $where[]='t.date<=?';$params[]=valid_date($_GET['to'],true).' 23:59:59'; }
            if (!empty($_GET['search'])) { $where[]='t.description LIKE ?';$params[]='%'.strval_checked($_GET['search']).'%'; }
            $rows=Database::all('SELECT t.*,f.name from_account_name,a.name to_account_name,a.currency to_currency FROM transfers t JOIN accounts f ON f.id=t.from_account_id JOIN accounts a ON a.id=t.to_account_id'.($where?' WHERE '.implode(' AND ',$where):'').' ORDER BY date DESC,id DESC',$params);
            foreach ($rows as &$r) { $r['amount']=major($r['amount']);$r['fee']=major($r['fee']);$r['received_amount']=major($r['received_amount']); } return $rows;
        }
        if ($resource === 'categories' || $resource === 'tags') {
            $where=[];$params=[];
            if (!empty($_GET['search'])) { $where[]='name LIKE ?';$params[]='%'.strval_checked($_GET['search']).'%'; }
            if ($resource==='categories' && !empty($_GET['type'])) { $where[]='type=?';$params[]=enum_value($_GET['type'],['income','expense'],'type'); }
            return Database::all('SELECT * FROM '.$resource.($where?' WHERE '.implode(' AND ',$where):'').' ORDER BY name',$params);
        }
        if ($resource === 'budgets') {
            $rows=Database::all('SELECT b.*,c.name category_name,c.icon category_icon,c.color category_color FROM budgets b JOIN categories c ON c.id=b.category_id ORDER BY month DESC,c.name');
            $out=[];
            foreach ($rows as $r) {
                if (!empty($_GET['month']) && $r['month']!==valid_month($_GET['month'])) continue;
                if (!empty($_GET['category_id']) && (int)$r['category_id']!==id_value($_GET['category_id'])) continue;
                if (!empty($_GET['search']) && stripos($r['category_name'],(string)$_GET['search'])===false) continue;
                $spent=(int)Database::scalar("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='expense' AND category_id IN (WITH RECURSIVE tree(id) AS (SELECT id FROM categories WHERE id=? UNION ALL SELECT c.id FROM categories c JOIN tree ON c.parent_id=tree.id) SELECT id FROM tree) AND currency=? AND substr(date,1,7)=?",[$r['category_id'],$r['currency'],$r['month']]);
                $cap=(int)$r['amount'];$r['percentage']=round($spent/$cap*100,1);$r['spent']=major($spent);$r['remaining']=major($cap-$spent);$r['amount']=major($cap);$r['status']=$spent>=$cap?'danger':($spent*100>=$cap*75?'warning':'healthy');$out[]=$r;
            } return $out;
        }
        if ($resource === 'debts') {
            $rows=Database::all('SELECT d.*,a.name account_name FROM debts d LEFT JOIN accounts a ON a.id=d.account_id ORDER BY due_date IS NULL,due_date,id DESC');$out=[];
            foreach ($rows as $r) {
                if (!empty($_GET['search']) && stripos($r['counterparty'].' '.$r['description'],(string)$_GET['search'])===false) continue;
                if (!empty($_GET['account_id']) && (int)$r['account_id']!==id_value($_GET['account_id'])) continue;
                if (!empty($_GET['from']) && $r['date']<valid_date($_GET['from'],true)) continue;
                if (!empty($_GET['to']) && substr($r['date'],0,10)>valid_date($_GET['to'],true)) continue;
                $r['payments']=Database::all('SELECT r.*,a.name account_name FROM repayments r JOIN accounts a ON a.id=r.account_id WHERE debt_id=? ORDER BY date DESC',[$r['id']]);
                $paid=0; foreach($r['payments'] as &$p){$paid+=(int)$p['amount'];$p['amount']=major($p['amount']);}unset($p);
                $r['remaining']=major((int)$r['amount']-$paid);$r['paid']=major($paid);$r['amount']=major($r['amount']);
                $r['status']=$r['remaining']<=0?'paid':($r['due_date'] && $r['due_date']<date('Y-m-d')?'overdue':'active');
                if (!empty($_GET['status']) && $r['status']!==$_GET['status']) continue;
                $out[]=$r;
            }return $out;
        }
        if ($resource === 'repayments') {
            $rows=Database::all('SELECT * FROM repayments'.(!empty($_GET['debt_id'])?' WHERE debt_id=?':'').' ORDER BY date DESC',!empty($_GET['debt_id'])?[id_value($_GET['debt_id'])]:[]);
            foreach($rows as &$r)$r['amount']=major($r['amount']); return $rows;
        }
        if ($resource === 'recurring') {
            $rows=Database::all('SELECT r.*,a.name account_name,a.currency,c.name category_name FROM recurring r JOIN accounts a ON a.id=r.account_id LEFT JOIN categories c ON c.id=r.category_id ORDER BY next_date');$out=[];
            foreach($rows as $r){if(!empty($_GET['search'])&&stripos($r['description'],(string)$_GET['search'])===false)continue;
                if(!empty($_GET['account_id'])&&(int)$r['account_id']!==id_value($_GET['account_id']))continue;
                if(!empty($_GET['from'])&&$r['next_date']<valid_date($_GET['from'],true))continue;
                if(!empty($_GET['to'])&&$r['next_date']>valid_date($_GET['to'],true))continue;
                if(isset($_GET['status'])&&$_GET['status']!==''&&((bool)$r['enabled'])!==($_GET['status']==='active'))continue;
                $r['amount']=major($r['amount']);$r['enabled']=(bool)$r['enabled'];$out[]=$r;} return $out;
        }
        if ($resource === 'users') return Database::all('SELECT id,name,email,role,active,created_at FROM users ORDER BY role DESC,name');
        return Database::all('SELECT l.*,u.name user_name FROM audit_logs l LEFT JOIN users u ON u.id=l.user_id ORDER BY l.id DESC LIMIT 500');
    }
    public static function mutate(string $resource,string $method,array $data): array
    {
        $user=Auth::requireUser();
        if (!in_array($resource,self::RESOURCES,true)) fail('Unknown resource.',404);
        if (in_array($resource,self::OWNER_RESOURCES,true) || $resource==='accounts') Auth::owner();
        if ($resource==='audit') fail('Audit logs are append-only.',403);
        $id=$method==='POST'?null:id_value($data['id']??null);
        return Database::atomic(function()use($resource,$method,$data,$id,$user){
            $existing=$id?Database::one('SELECT * FROM '.$resource.' WHERE id=?',[$id]):null;
            if($id&&!$existing)fail('Record not found.',404);
            if($method==='DELETE'){
                if($resource==='users')fail('Deactivate a user to preserve their audit history.');
                Database::query('DELETE FROM '.$resource.' WHERE id=?',[$id]);Database::audit('delete',$resource,$id);return ['deleted'=>$id];
            }
            $old=$existing??[];
            foreach(['amount','received_amount','fee','initial_balance','target_amount'] as $field)if(isset($old[$field]))$old[$field]=number_format(major($old[$field]),2,'.','');
            $d=array_merge($old,$data); $record=[];
            if($resource==='accounts'){
                $record=['name'=>required_text($d,'name',100),'type'=>enum_value($d['type']??'', ['bank','card','cash','savings','digital'],'account type'),'currency'=>currency($d['currency']??'USD'),'initial_balance'=>money($d['initial_balance']??0),'icon'=>strval_checked($d['icon']??'wallet',60),'color'=>valid_color($d['color']??'#10b981'),'status'=>enum_value($d['status']??'active',['active','archived'],'status'),'details'=>strval_checked($d['details']??'',2000),'target_amount'=>money($d['target_amount']??0)];
                if($record['target_amount']<0)fail('Savings target cannot be negative.');
                if($existing&&$record['currency']!==$existing['currency']){
                    $count=(int)Database::scalar('SELECT (SELECT COUNT(*) FROM transactions WHERE account_id=?)+(SELECT COUNT(*) FROM transfers WHERE from_account_id=? OR to_account_id=?)+(SELECT COUNT(*) FROM debts WHERE account_id=?)+(SELECT COUNT(*) FROM repayments WHERE account_id=?)+(SELECT COUNT(*) FROM recurring WHERE account_id=?)',array_fill(0,6,$id));
                    if($count)fail('Currency cannot change after an account has financial activity.');
                }
            }elseif($resource==='transactions'){
                $a=self::account(id_value($d['account_id']??null),!$existing||($existing['account_id']!=$d['account_id']));
                $type=enum_value($d['type']??'expense',['income','expense'],'transaction type');$category=!empty($d['category_id'])?id_value($d['category_id']):null;self::category($category,$type);
                $curr=currency($d['currency']??$a['currency']);if($curr!==$a['currency'])fail('Transaction currency must match its account.');
                $record=['type'=>$type,'amount'=>money($d['amount']??0,true),'currency'=>$curr,'account_id'=>$a['id'],'category_id'=>$category,'date'=>valid_date($d['date']??date('Y-m-d H:i:s')),'description'=>strval_checked($d['description']??'',2000),'receipt'=>strval_checked($d['receipt']??'',1000)];
                if(!$id)$record['created_by']=$user['id'];
            }elseif($resource==='transfers'){
                $from=self::account(id_value($d['from_account_id']??null),!$existing||$existing['from_account_id']!=$d['from_account_id']);$to=self::account(id_value($d['to_account_id']??null),!$existing||$existing['to_account_id']!=$d['to_account_id']);
                if($from['id']===$to['id'])fail('Choose two different accounts.');
                $amount=money($d['amount']??0,true);
                $received=$amount;
                if($from['currency']!==$to['currency']) {
                    if(!array_key_exists('received_amount',$data)&&(!$existing||$existing['from_account_id']!=$from['id']||$existing['to_account_id']!=$to['id']||array_key_exists('amount',$data)))fail('Enter the explicit received amount in the destination currency for a cross-currency transfer.');
                    $received=money($d['received_amount']??0,true);
                } elseif(array_key_exists('received_amount',$data)&&money($data['received_amount'],true)!==$amount)fail('Same-currency transfers must receive the full transfer amount; enter commission separately.');
                $fee=money($d['fee']??0);if($fee<0)fail('Fee cannot be negative.');
                $record=['from_account_id'=>$from['id'],'to_account_id'=>$to['id'],'amount'=>$amount,'received_amount'=>$received,'fee'=>$fee,'currency'=>$from['currency'],'date'=>valid_date($d['date']??date('Y-m-d H:i:s')),'description'=>strval_checked($d['description']??'',2000)];if(!$id)$record['created_by']=$user['id'];
            }elseif($resource==='categories'){
                $type=enum_value($d['type']??'expense',['income','expense'],'category type');$parent=!empty($d['parent_id'])?id_value($d['parent_id']):null;
                self::category($parent,$type);
                $visited=[];$cursor=$parent;while($cursor){if($cursor===$id||isset($visited[$cursor]))fail('Category hierarchy cannot contain a cycle.');$visited[$cursor]=true;$p=self::category($cursor);$cursor=$p['parent_id']?(int)$p['parent_id']:null;}
                if($existing&&$type!==$existing['type']){
                    $uses=(int)Database::scalar('SELECT (SELECT COUNT(*) FROM transactions WHERE category_id=?)+(SELECT COUNT(*) FROM recurring WHERE category_id=?)+(SELECT COUNT(*) FROM budgets WHERE category_id=?)+(SELECT COUNT(*) FROM categories WHERE parent_id=?)',array_fill(0,4,$id));if($uses)fail('This category type is in use and cannot change.');
                }
                $record=['name'=>required_text($d,'name',100),'type'=>$type,'parent_id'=>$parent,'icon'=>strval_checked($d['icon']??'tag',60),'color'=>valid_color($d['color']??'#10b981')];
            }elseif($resource==='tags'){
                $record=['name'=>required_text($d,'name',60),'color'=>valid_color($d['color']??'#06b6d4')];
            }elseif($resource==='budgets'){
                $category=id_value($d['category_id']??null);self::category($category,'expense');
                $record=['category_id'=>$category,'amount'=>money($d['amount']??0,true),'currency'=>currency($d['currency']??'USD'),'month'=>valid_month($d['month']??date('Y-m'))];
            }elseif($resource==='debts'){
                $curr=currency($d['currency']??'USD');$account=!empty($d['account_id'])?self::account(id_value($d['account_id']),!$existing||$existing['account_id']!=$d['account_id']):null;if($account&&$account['currency']!==$curr)fail('Debt and account currencies must match.');
                $amount=money($d['amount']??0,true);$paid=$id?(int)Database::scalar('SELECT COALESCE(SUM(amount),0) FROM repayments WHERE debt_id=?',[$id]):0;if($amount<$paid)fail('Principal cannot be less than repayments already recorded.');
                $direction=enum_value($d['direction']??'lending',['borrowing','lending'],'debt direction');
                if($existing&&$paid>0&&($direction!==$existing['direction']||$curr!==$existing['currency']))fail('A debt with repayments cannot change direction or currency.');
                $record=['direction'=>$direction,'counterparty'=>required_text($d,'counterparty',150),'contact'=>strval_checked($d['contact']??'',200),'amount'=>$amount,'currency'=>$curr,'account_id'=>$account['id']??null,'date'=>valid_date($d['date']??date('Y-m-d H:i:s')),'due_date'=>!empty($d['due_date'])?valid_date($d['due_date'],true):null,'description'=>strval_checked($d['description']??'',2000)];if(!$id)$record['created_by']=$user['id'];
            }elseif($resource==='repayments'){
                $debtId=id_value($d['debt_id']??null);$debt=Database::one('SELECT * FROM debts WHERE id=?',[$debtId]);if(!$debt)fail('Debt not found.',404);
                $a=self::account(id_value($d['account_id']??null),!$existing||$existing['account_id']!=$d['account_id']);if($a['currency']!==$debt['currency'])fail('Repayment and debt currencies must match.');
                $amount=money($d['amount']??0,true);$paid=(int)Database::scalar('SELECT COALESCE(SUM(amount),0) FROM repayments WHERE debt_id=? AND id<>?',[$debtId,$id??0]);if($paid+$amount>(int)$debt['amount'])fail('Repayment exceeds the remaining principal.');
                $record=['debt_id'=>$debtId,'account_id'=>$a['id'],'amount'=>$amount,'date'=>valid_date($d['date']??date('Y-m-d H:i:s')),'description'=>strval_checked($d['description']??'',2000)];if(!$id)$record['created_by']=$user['id'];
            }elseif($resource==='recurring'){
                $a=self::account(id_value($d['account_id']??null),!$existing||$existing['account_id']!=$d['account_id']);$type=enum_value($d['type']??'expense',['income','expense'],'transaction type');$category=!empty($d['category_id'])?id_value($d['category_id']):null;self::category($category,$type);
                $next=valid_date($d['next_date']??date('Y-m-d'),true);$resetAnchor=!$existing||isset($data['next_date']);
                $record=['type'=>$type,'amount'=>money($d['amount']??0,true),'account_id'=>$a['id'],'category_id'=>$category,'description'=>strval_checked($d['description']??'',2000),'frequency'=>enum_value($d['frequency']??'monthly',['daily','weekly','monthly','annual'],'frequency'),'next_date'=>$next,'enabled'=>filter_var($d['enabled']??true,FILTER_VALIDATE_BOOLEAN)?1:0,'anchor_day'=>$resetAnchor?(int)substr($next,8,2):(int)$existing['anchor_day'],'anchor_month'=>$resetAnchor?(int)substr($next,5,2):(int)$existing['anchor_month']];if(!$id)$record['created_by']=$user['id'];
            }elseif($resource==='users'){
                if($existing&&$existing['role']==='owner')fail('Use your profile password screen to manage the owner account.');
                $record=['name'=>required_text($d,'name',100),'email'=>Auth::email($d['email']??''),'role'=>'assistant','active'=>filter_var($d['active']??true,FILTER_VALIDATE_BOOLEAN)?1:0];
                if(!$id||!empty($data['password']))$record['password_hash']=password_hash(Auth::validatePassword($data['password']??null),PASSWORD_BCRYPT,['cost'=>12]);
                if($id)$record['auth_version']=(int)$existing['auth_version']+1;
            }
            // An explicitly edited example becomes the user's own record.
            if($id&&$resource!=='users')$record['is_demo']=0;
            if($id)Database::update($resource,$id,$record);else $id=Database::insert($resource,$record);
            if($resource==='transactions'&&array_key_exists('tags',$data))self::setTags($id,$data['tags']);
            Database::audit($method==='POST'?'create':'update',$resource,$id);
            $saved=$_GET;$_GET=[];
            try{foreach(self::listing($resource)as$r)if((int)$r['id']===$id)return $r;}finally{$_GET=$saved;}
            return ['id'=>$id];
        });
    }
    private static function setTags(int $transactionId,mixed $tags):void
    {
        if(!is_array($tags)||count($tags)>20)fail('Tags must be a list of at most 20 names.');
        foreach($tags as $tagName) if(!is_string($tagName))fail('Tags must be a list of at most 20 names.');
        Database::query('DELETE FROM transaction_tags WHERE transaction_id=?',[$transactionId]);
        foreach(array_unique($tags)as$name){$name=strval_checked($name,60);if($name==='')continue;Database::query('INSERT INTO tags(name) VALUES(?) ON CONFLICT(name) DO NOTHING',[$name]);$tag=(int)Database::scalar('SELECT id FROM tags WHERE name=? COLLATE NOCASE',[$name]);Database::query('INSERT OR IGNORE INTO transaction_tags(transaction_id,tag_id) VALUES(?,?)',[$transactionId,$tag]);}
    }
    public static function nextOccurrence(array $r,string $current):string
    {
        $date=new DateTimeImmutable($current);
        if($r['frequency']==='daily')return $date->modify('+1 day')->format('Y-m-d');
        if($r['frequency']==='weekly')return $date->modify('+7 days')->format('Y-m-d');
        if($r['frequency']==='monthly'){$next=$date->modify('first day of next month');$day=min((int)$r['anchor_day'],(int)$next->format('t'));return $next->setDate((int)$next->format('Y'),(int)$next->format('m'),$day)->format('Y-m-d');}
        $year=(int)$date->format('Y')+1;$month=(int)$r['anchor_month'];$base=new DateTimeImmutable(sprintf('%04d-%02d-01',$year,$month));return $base->setDate($year,$month,min((int)$r['anchor_day'],(int)$base->format('t')))->format('Y-m-d');
    }
    public static function processRecurring():array
    {
        $user=Auth::requireUser();
        return Database::atomic(function()use($user){$count=0;$today=date('Y-m-d');
            foreach(Database::all("SELECT r.*,a.currency,a.status FROM recurring r JOIN accounts a ON a.id=r.account_id WHERE r.enabled=1 AND r.next_date<=? ORDER BY next_date",[$today])as$r){
                if($r['status']!=='active')continue;$next=$r['next_date'];$iterations=0;
                while($next<=$today){
                    if(++$iterations>3660)fail('Recurring backlog exceeds 10 years. Update its next date before processing.');
                    Database::query('INSERT OR IGNORE INTO transactions(type,amount,currency,account_id,category_id,date,description,recurring_id,occurrence_date,created_by,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?,?)',[$r['type'],$r['amount'],$r['currency'],$r['account_id'],$r['category_id'],$next.' 09:00:00',$r['description'],$r['id'],$next,$user['id'],(int)($r['is_demo']??0)]);
                    $count+=Database::query('SELECT changes()')->fetchColumn();$next=self::nextOccurrence($r,$next);
                }Database::update('recurring',(int)$r['id'],['next_date'=>$next]);
            }Database::audit('process_recurring','recurring');return ['processed'=>(int)$count];
        });
    }
    public static function summary():array
    {
        Auth::owner();$balances=self::balances();$totals=[];
        foreach(SUPPORTED_CURRENCIES as $cur)$totals[$cur]=['currency'=>$cur,'balance'=>0,'income'=>0,'expense'=>0,'net'=>0,'receivables'=>0,'payables'=>0,'net_worth'=>0];
        foreach(Database::all('SELECT id,currency FROM accounts')as$a)$totals[$a['currency']]['balance']+=$balances[$a['id']]??0;
        foreach(Database::all("SELECT currency,type,SUM(amount) amount FROM transactions WHERE substr(date,1,7)=? GROUP BY currency,type",[date('Y-m')])as$r)$totals[$r['currency']][$r['type']]+=(int)$r['amount'];
        foreach(Database::all("SELECT currency,SUM(fee) fees FROM transfers WHERE substr(date,1,7)=? GROUP BY currency",[date('Y-m')])as$r)$totals[$r['currency']]['expense']+=(int)$r['fees'];
        foreach(Database::all('SELECT d.*,COALESCE((SELECT SUM(amount) FROM repayments WHERE debt_id=d.id),0) paid FROM debts d')as$d)$totals[$d['currency']][$d['direction']==='lending'?'receivables':'payables']+=(int)$d['amount']-(int)$d['paid'];
        foreach($totals as &$t){$t['net']=$t['income']-$t['expense'];$t['net_worth']=$t['balance']+$t['receivables']-$t['payables'];foreach(['balance','income','expense','net','receivables','payables','net_worth']as$f)$t[$f]=major($t[$f]);}unset($t);
        return ['currencies'=>array_values($totals),'transaction_count'=>(int)Database::scalar('SELECT COUNT(*) FROM transactions'),'account_count'=>(int)Database::scalar("SELECT COUNT(*) FROM accounts WHERE status='active'")];
    }
    private static function ledger(string $cur):array
    {
        $events=[];
        foreach(Database::all('SELECT date,type,amount FROM transactions WHERE currency=?',[$cur])as$r)$events[]=['date'=>substr($r['date'],0,10),'amount'=>($r['type']==='income'?1:-1)*(int)$r['amount']];
        foreach(Database::all('SELECT t.*,a.currency to_currency FROM transfers t JOIN accounts a ON a.id=t.to_account_id WHERE t.currency=? OR a.currency=?',[$cur,$cur])as$r) {
            $delta=($r['currency']===$cur?-(int)$r['amount']-(int)$r['fee']:0)+($r['to_currency']===$cur?(int)$r['received_amount']:0);
            if($delta!==0)$events[]=['date'=>substr($r['date'],0,10),'amount'=>$delta];
        }
        foreach(Database::all('SELECT date,direction,amount FROM debts WHERE currency=? AND account_id IS NOT NULL',[$cur])as$r)$events[]=['date'=>substr($r['date'],0,10),'amount'=>($r['direction']==='borrowing'?1:-1)*(int)$r['amount']];
        foreach(Database::all('SELECT r.date,r.amount,d.direction FROM repayments r JOIN debts d ON d.id=r.debt_id WHERE d.currency=?',[$cur])as$r)$events[]=['date'=>substr($r['date'],0,10),'amount'=>($r['direction']==='lending'?1:-1)*(int)$r['amount']];
        return $events;
    }
    public static function analytics(string $cur):array
    {
        Auth::owner();$cur=currency($cur);$allBalances=self::balances();$balance=0;$distribution=[];
        foreach(Database::all('SELECT id,type FROM accounts WHERE currency=?',[$cur])as$a){$value=$allBalances[$a['id']]??0;$balance+=$value;$distribution[$a['type']]=($distribution[$a['type']]??0)+$value;}
        $monthly=[];$first=new DateTimeImmutable('first day of -5 months');
        for($i=0;$i<6;$i++){$key=$first->modify("+$i months")->format('Y-m');$monthly[$key]=['month'=>$key,'income'=>0,'expense'=>0];}
        foreach(Database::all('SELECT substr(date,1,7) month,type,SUM(amount) amount FROM transactions WHERE currency=? AND date>=? GROUP BY month,type',[$cur,$first->format('Y-m-d')])as$r)if(isset($monthly[$r['month']]))$monthly[$r['month']][$r['type']]=major($r['amount']);
        foreach(Database::all('SELECT substr(date,1,7) month,SUM(fee) fees FROM transfers WHERE currency=? AND date>=? GROUP BY month',[$cur,$first->format('Y-m-d')])as$r)if(isset($monthly[$r['month']]))$monthly[$r['month']]['expense']+=major($r['fees']);
        $start=(new DateTimeImmutable('today'))->modify('-29 days');$daily=[];
        for($i=0;$i<30;$i++){$key=$start->modify("+$i days")->format('Y-m-d');$daily[$key]=['date'=>$key,'income'=>0,'expense'=>0,'delta'=>0];}
        $events=self::ledger($cur);$net=0;
        foreach($events as$event)if(isset($daily[$event['date']])){$daily[$event['date']]['delta']+=$event['amount'];$net+=$event['amount'];}
        foreach(Database::all('SELECT substr(date,1,10) day,type,SUM(amount) amount FROM transactions WHERE currency=? AND date>=? GROUP BY day,type',[$cur,$start->format('Y-m-d')])as$r)if(isset($daily[$r['day']]))$daily[$r['day']][$r['type']]=major($r['amount']);
        foreach(Database::all('SELECT substr(date,1,10) day,SUM(fee) fees FROM transfers WHERE currency=? AND date>=? GROUP BY day',[$cur,$start->format('Y-m-d')])as$r)if(isset($daily[$r['day']]))$daily[$r['day']]['expense']+=major($r['fees']);
        $running=$balance-$net;
        foreach($daily as&$d){$running+=$d['delta'];$d['balance']=major($running);unset($d['delta']);}unset($d);
        // Median of complete daily discretionary spending, including zero-spend days.
        // Recurring-generated entries are excluded because schedules are projected separately.
        $spending=array_fill_keys(array_keys($daily),0);
        foreach(Database::all("SELECT substr(date,1,10) day,SUM(amount) amount FROM transactions WHERE currency=? AND type='expense' AND recurring_id IS NULL AND date>=? AND substr(date,1,10)<? GROUP BY day",[$cur,$start->format('Y-m-d'),date('Y-m-d')])as$r)if(isset($spending[$r['day']]))$spending[$r['day']]=(int)$r['amount'];
        foreach(Database::all('SELECT substr(date,1,10) day,SUM(fee) fees FROM transfers WHERE currency=? AND date>=? AND substr(date,1,10)<? GROUP BY day',[$cur,$start->format('Y-m-d'),date('Y-m-d')])as$r)if(isset($spending[$r['day']]))$spending[$r['day']]+=(int)$r['fees'];
        unset($spending[date('Y-m-d')]);$values=array_values($spending);sort($values);$n=count($values);$median=$n?($n%2?$values[intdiv($n,2)]:($values[$n/2-1]+$values[$n/2])/2):0;
        $scheduled=[];$today=date('Y-m-d');$end=(new DateTimeImmutable('today'))->modify('+90 days')->format('Y-m-d');
        foreach(Database::all("SELECT r.* FROM recurring r JOIN accounts a ON a.id=r.account_id WHERE r.enabled=1 AND a.status='active' AND a.currency=?",[$cur])as$r){$next=$r['next_date'];$iterations=0;while($next<=$end&&++$iterations<=4000){if(!Database::scalar('SELECT id FROM transactions WHERE recurring_id=? AND occurrence_date=?',[$r['id'],$next]))$scheduled[]=['date'=>max($today,$next),'amount'=>(int)$r['amount'],'type'=>$r['type']];$next=self::nextOccurrence($r,$next);}}
        foreach(Database::all('SELECT d.*,COALESCE((SELECT SUM(amount) FROM repayments WHERE debt_id=d.id),0) paid FROM debts d WHERE currency=? AND due_date IS NOT NULL AND due_date<=?',[$cur,$end])as$d){$remaining=(int)$d['amount']-(int)$d['paid'];if($remaining>0)$scheduled[]=['date'=>max($today,$d['due_date']),'amount'=>$remaining,'type'=>$d['direction']==='lending'?'income':'expense'];}
        $forecast=[];
        foreach([30,60,90]as$days){$limit=(new DateTimeImmutable('today'))->modify("+$days days")->format('Y-m-d');$income=0;$expense=0;foreach($scheduled as$s)if($s['date']<=$limit){if($s['type']==='income')$income+=$s['amount'];else$expense+=$s['amount'];}$forecast[]=['days'=>$days,'balance'=>major((int)round($balance-$median*$days+$income-$expense)),'scheduled_income'=>major($income),'scheduled_expense'=>major($expense),'daily_median'=>major((int)round($median))];}
        $current=$monthly[date('Y-m')]??['income'=>0,'expense'=>0];
        return ['currency'=>$cur,'balance'=>major($balance),'income'=>$current['income'],'expense'=>$current['expense'],'monthly'=>array_values($monthly),'cashflow'=>array_values($daily),'distribution'=>array_map(static fn($type,$value)=>['type'=>$type,'balance'=>major($value)],array_keys($distribution),array_values($distribution)),'forecast'=>$forecast,'forecast_method'=>'Median of the previous 29 complete days of non-recurring expenses, plus scheduled recurring entries and unpaid debts due within each horizon. Zero-spend days are included; currencies remain separate.'];
    }
    public static function setup(array $data):array
    {
        $name=required_text($data,'name',100);$email=Auth::email($data['email']??'');$password=Auth::validatePassword($data['password']??null);
        Database::atomic(function()use($name,$email,$password,$data){
            if((int)Database::scalar('SELECT COUNT(*) FROM users')!==0)fail('Setup has already been completed.',409);
            $id=Database::insert('users',['name'=>$name,'email'=>$email,'password_hash'=>password_hash($password,PASSWORD_BCRYPT,['cost'=>12]),'role'=>'owner']);
            $user=Database::one('SELECT * FROM users WHERE id=?',[$id]);Auth::signIn($user);Database::audit('setup','users',$id);
            if(filter_var($data['demo']??false,FILTER_VALIDATE_BOOLEAN))self::seed($id);
        });return Auth::session();
    }
    private static function seed(int $userId):void
    {
        $cats=[];
        foreach([['Client payments','income','briefcase','#10b981'],['Salary','income','badge-dollar-sign','#06b6d4'],['Investments','income','trending-up','#8b5cf6'],['Food & dining','expense','utensils','#f59e0b'],['Shopping','expense','shopping-bag','#a78bfa'],['Transport','expense','car','#06b6d4'],['Subscriptions','expense','repeat','#ec4899'],['Office & tools','expense','laptop','#3b82f6'],['Travel','expense','plane','#14b8a6'],['Utilities','expense','zap','#f97316']]as$c)$cats[$c[0]]=Database::insert('categories',['is_demo'=>1,'name'=>$c[0],'type'=>$c[1],'icon'=>$c[2],'color'=>$c[3]]);
        $accounts=[];
        foreach([['Business account','bank','USD',2864050,'landmark','#10b981','Mercury · Business checking'],['Everyday card','card','USD',428000,'credit-card','#8b5cf6','Visa · •••• 4829'],['Cash wallet','cash','USD',48000,'wallet','#f59e0b','Everyday cash'],['Rainy day fund','savings','USD',1200000,'vault','#06b6d4','Emergency savings'],['Humo card','card','UZS',685000000,'credit-card','#3b82f6','Humo · •••• 0916']]as$a){$accounts[$a[0]]=Database::insert('accounts',['is_demo'=>1,'name'=>$a[0],'type'=>$a[1],'currency'=>$a[2],'initial_balance'=>$a[3],'icon'=>$a[4],'color'=>$a[5],'details'=>$a[6],'target_amount'=>$a[0]==='Rainy day fund'?2500000:0]);}
        foreach([['business','#06b6d4'],['personal','#a78bfa'],['essential','#f59e0b']]as$t)Database::insert('tags',['is_demo'=>1,'name'=>$t[0],'color'=>$t[1]]);
        $month=new DateTimeImmutable('first day of this month');
        for($m=5;$m>=0;$m--){$base=$month->modify("-$m months");$lastDay=$m===0?(int)date('j'):(int)$base->format('t');
            $rows=[['income',580000+$m*17000,'Business account','Client payments',2,'Brand strategy · Northstar Studio'],['income',225000+$m*9000,'Business account','Client payments',12,'Website project · Acme Co.'],['expense',8900,'Everyday card','Subscriptions',3,'Figma Professional'],['expense',14900,'Business account','Office & tools',5,'Workspace membership'],['expense',4250,'Everyday card','Food & dining',7,'Dinner at Basil & Co.'],['expense',12000,'Everyday card','Shopping',9,'Everyday essentials'],['expense',2850,'Everyday card','Transport',11,'Fuel & transport'],['expense',6800,'Business account','Utilities',14,'Internet & utilities'],['expense',3650,'Everyday card','Food & dining',16,'Coffee & lunch'],['income',145000,'Business account','Client payments',18,'Monthly retainer · Linear Labs']];
            foreach($rows as$r){if($r[4]>$lastDay)continue;$date=$base->setDate((int)$base->format('Y'),(int)$base->format('m'),$r[4])->format('Y-m-d').' 12:30:00';$tx=Database::insert('transactions',['is_demo'=>1,'type'=>$r[0],'amount'=>$r[1],'currency'=>'USD','account_id'=>$accounts[$r[2]],'category_id'=>$cats[$r[3]],'date'=>$date,'description'=>$r[5],'created_by'=>$userId]);self::setTags($tx,[$r[2]==='Business account'?'business':'personal']);}
        }
        Database::insert('transactions',['is_demo'=>1,'type'=>'expense','amount'=>25500000,'currency'=>'UZS','account_id'=>$accounts['Humo card'],'category_id'=>$cats['Food & dining'],'date'=>date('Y-m-d').' 10:15:00','description'=>'Grocery shopping','created_by'=>$userId]);
        Database::insert('transfers',['is_demo'=>1,'from_account_id'=>$accounts['Business account'],'to_account_id'=>$accounts['Rainy day fund'],'amount'=>125000,'received_amount'=>125000,'fee'=>0,'currency'=>'USD','date'=>date('Y-m-d',strtotime('-3 days')).' 14:00:00','description'=>'Monthly savings allocation','created_by'=>$userId]);
        foreach([['Food & dining',50000],['Shopping',35000],['Transport',15000],['Subscriptions',18000],['Office & tools',50000]]as$b)Database::insert('budgets',['is_demo'=>1,'category_id'=>$cats[$b[0]],'amount'=>$b[1],'currency'=>'USD','month'=>date('Y-m')]);
        $debt=Database::insert('debts',['is_demo'=>1,'direction'=>'lending','counterparty'=>'Alex Morgan','contact'=>'alex@example.com','amount'=>120000,'currency'=>'USD','account_id'=>$accounts['Business account'],'date'=>date('Y-m-d',strtotime('-18 days')).' 09:00:00','due_date'=>date('Y-m-d',strtotime('+12 days')),'description'=>'Equipment advance','created_by'=>$userId]);
        Database::insert('repayments',['is_demo'=>1,'debt_id'=>$debt,'account_id'=>$accounts['Business account'],'amount'=>40000,'date'=>date('Y-m-d',strtotime('-4 days')).' 10:00:00','description'=>'First installment','created_by'=>$userId]);
        Database::insert('debts',['is_demo'=>1,'direction'=>'borrowing','counterparty'=>'Studio equipment finance','contact'=>'finance@example.com','amount'=>250000,'currency'=>'USD','account_id'=>null,'date'=>date('Y-m-d',strtotime('-30 days')).' 09:00:00','due_date'=>date('Y-m-d',strtotime('+35 days')),'description'=>'Remaining equipment payment','created_by'=>$userId]);
        foreach([['expense',8900,'Everyday card','Subscriptions','Figma Professional','monthly','+15 days'],['expense',14900,'Business account','Office & tools','Workspace membership','monthly','+17 days'],['income',580000,'Business account','Client payments','Northstar monthly retainer','monthly','+14 days'],['expense',2400,'Everyday card','Subscriptions','Cloud storage','monthly','+5 days']]as$r){$next=date('Y-m-d',strtotime($r[6]));Database::insert('recurring',['is_demo'=>1,'type'=>$r[0],'amount'=>$r[1],'account_id'=>$accounts[$r[2]],'category_id'=>$cats[$r[3]],'description'=>$r[4],'frequency'=>$r[5],'next_date'=>$next,'enabled'=>1,'anchor_day'=>(int)substr($next,8,2),'anchor_month'=>(int)substr($next,5,2),'created_by'=>$userId]);}
        Database::audit('seed_demo','database');
    }
}
