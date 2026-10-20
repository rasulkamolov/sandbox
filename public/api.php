<?php
declare(strict_types=1);
ini_set('display_errors', '0');
ini_set('log_errors', '1');

require_once __DIR__ . '/../src/Hosting.php';
$hostingIssues = Hosting::problems();
if ($hostingIssues) {
    http_response_code(503);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode(['ok' => false, 'error' => implode(' ', $hostingIssues)]);
    exit;
}

require_once __DIR__ . '/../config/config.php';
require_once APP_ROOT . '/src/Helpers.php';
require_once APP_ROOT . '/src/Database.php';
require_once APP_ROOT . '/src/Auth.php';
require_once APP_ROOT . '/src/Finance.php';
require_once APP_ROOT . '/src/DemoData.php';
require_once APP_ROOT . '/src/Reports.php';

header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: same-origin');

try {
    Auth::start();
    foreach ($_GET as $queryValue) if (!is_string($queryValue)) fail('Invalid query parameter.');
    $method=$_SERVER['REQUEST_METHOD']??'GET';
    $action=is_string($_GET['action']??null)?$_GET['action']:'session';
    if(!in_array($method,['GET','POST','PUT','DELETE'],true))fail('Method not allowed.',405);
    if($method!=='GET')Auth::csrf();
    $data=$method==='GET'?[]:input();
    if($action==='session'&&$method==='GET')respond(Auth::session());
    if($action==='setup'&&$method==='POST')respond(Finance::setup($data),201);
    if($action==='login'&&$method==='POST')respond(Auth::login($data));
    if($action==='locale'&&$method==='POST'){
        $_SESSION['locale']=enum_value($data['locale']??'',SUPPORTED_LOCALES,'language');respond(['locale'=>$_SESSION['locale']]);
    }
    $user=Auth::requireUser();
    if($action==='logout'&&$method==='POST'){Database::audit('logout','users',(int)$user['id']);Auth::clear();respond(Auth::session());}
    if($action==='bootstrap'&&$method==='GET'){
        $result=Finance::bootstrap();
        if($user['role']==='owner')$result['demo_status']=DemoData::status();
        respond($result);
    }
    if($action==='demo_status'&&$method==='GET')respond(DemoData::status());
    if($action==='clear_sample_data'&&$method==='POST')respond(DemoData::clear($data));
    if($action==='reset_finances'&&$method==='POST')respond(DemoData::reset($data));
    if($action==='reports'&&$method==='GET')respond(Reports::build($_GET));
    if($action==='report_export'&&$method==='GET'){
        $export=Reports::export($_GET);
        Database::audit('export_report','reports');
        header('Content-Type: text/csv; charset=utf-8');
        header('Content-Disposition: attachment; filename="vela-report-'.date('Y-m-d').'.csv"');
        $out=fopen('php://output','w');fwrite($out,"\xEF\xBB\xBF");
        foreach([$export['headers'],...$export['rows']]as$row){
            $safe=array_map(static fn($value)=>is_int($value)||is_float($value)?$value:csv_safe($value),$row);
            fputcsv($out,$safe,',','"','');
        }
        fclose($out);exit;
    }
    if($action==='analytics'&&$method==='GET')respond(Finance::analytics(currency($_GET['currency']??'USD')));
    if($action==='process_recurring'&&$method==='POST')respond(Finance::processRecurring());
    if($action==='password'&&$method==='POST'){
        $new=Auth::validatePassword($data['new_password']??null);
        $row=Database::atomic(function()use($user,$data,$new){
            $row=Database::one('SELECT * FROM users WHERE id=?',[$user['id']]);
            if(!is_string($data['current_password']??null)||!password_verify($data['current_password'],$row['password_hash']))fail('Current password is incorrect.',403);
            Database::update('users',(int)$user['id'],['password_hash'=>password_hash($new,PASSWORD_BCRYPT,['cost'=>12]),'auth_version'=>(int)$row['auth_version']+1]);Database::audit('change_password','users',(int)$user['id']);
            $row['auth_version']++;return $row;
        });
        Auth::signIn($row);respond(['changed'=>true,'csrf'=>$_SESSION['csrf']]);
    }
    if($action==='export'&&$method==='GET'){
        $type=enum_value($_GET['type']??'transactions',['transactions','accounts','transfers','budgets','debts'],'export type');
        $GLOBALS['finance_export']=true;unset($_GET['type']);$rows=Finance::listing($type);Database::audit('export',$type);
        header('Content-Type: text/csv; charset=utf-8');header('Content-Disposition: attachment; filename="vela-'.$type.'-'.date('Y-m-d').'.csv"');
        $out=fopen('php://output','w');fwrite($out,"\xEF\xBB\xBF");
        if($rows){$keys=array_keys($rows[0]);fputcsv($out,$keys,',','"','');foreach($rows as$row){$values=[];foreach($keys as$key){$v=$row[$key]??'';$values[]=csv_safe(is_array($v)?json_encode($v,JSON_UNESCAPED_UNICODE):$v);}fputcsv($out,$values,',','"','');}}else fputcsv($out,['No records'],',','"','');
        fclose($out);exit;
    }
    if($action==='backup'&&$method==='GET'){
        Auth::owner();Database::audit('backup','database');
        $temp=tempnam(sys_get_temp_dir(),'vela-backup-');if($temp===false)throw new RuntimeException('Backup storage is unavailable.');unlink($temp);
        try{Database::query('VACUUM INTO ?',[$temp]);@chmod($temp,0600);header('Content-Type: application/vnd.sqlite3');header('Content-Disposition: attachment; filename="vela-backup-'.date('Y-m-d-His').'.db"');header('Content-Length: '.filesize($temp));readfile($temp);}finally{if(is_file($temp))unlink($temp);}exit;
    }
    if($action==='receipts'){$action='transactions';if($method==='GET'){$rows=Finance::listing('transactions');respond(array_values(array_filter($rows,static fn($row)=>$row['receipt']!=='')));}}
    if($method==='GET')respond(Finance::listing($action));
    respond(Finance::mutate($action,$method,$data),$method==='POST'?201:200);
} catch(ApiException $e){
    http_response_code($e->status);header('Content-Type: application/json; charset=utf-8');echo json_encode(['ok'=>false,'error'=>$e->getMessage()],JSON_UNESCAPED_UNICODE|JSON_INVALID_UTF8_SUBSTITUTE);
} catch(PDOException $e){
    $conflict=str_contains($e->getMessage(),'UNIQUE constraint failed');$references=str_contains($e->getMessage(),'FOREIGN KEY constraint failed');
    http_response_code($conflict||$references?409:500);header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok'=>false,'error'=>$conflict?'A record with these details already exists.':($references?'This record is in use. Archive it or remove its dependent records first.':'A database error occurred. Please try again.')]);
    if(!$conflict&&!$references)error_log('Vela database error: '.$e->getMessage());
} catch(Throwable $e){
    error_log('Vela error: '.$e->getMessage());http_response_code(500);header('Content-Type: application/json; charset=utf-8');echo json_encode(['ok'=>false,'error'=>'An unexpected error occurred. Please try again.']);
}
