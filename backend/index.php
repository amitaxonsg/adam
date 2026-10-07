<?php
declare(strict_types=1);
/**
 * Adam questionnaire submission API (PHP 8+, PDO SQLite).
 * Deploy to a PHP-enabled host, NOT to GitHub Pages.
 * Environment variables:
 * ADAM_ADMIN_TOKEN: long random secret, used solely for export/list (never in public JS).
 * ADAM_ALLOWED_ORIGIN: https://amitaxonsg.github.io
 * ADAM_DB_PATH: absolute path outside the web/document root (must be writable).
 */
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
$allowed = getenv('ADAM_ALLOWED_ORIGIN') ?: 'https://amitaxonsg.github.io';
if ($origin === $allowed) {
    header('Access-Control-Allow-Origin: ' . $allowed);
    header('Vary: Origin');
    header('Access-Control-Allow-Methods: POST, GET, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type, Authorization');
}
function respond(int $code, array $payload): never {
    http_response_code($code); echo json_encode($payload, JSON_UNESCAPED_SLASHES); exit;
}
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') {
    if ($origin !== $allowed) respond(403, ['error'=>'Origin not allowed']);
    http_response_code(204); exit;
}
$dbPath = getenv('ADAM_DB_PATH') ?: '';
if (!$dbPath || !str_starts_with($dbPath, '/') || !extension_loaded('pdo_sqlite')) {
    respond(503, ['error'=>'Submission service not configured']);
}
try {
    $db = new PDO('sqlite:' . $dbPath, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_TIMEOUT => 5]);
    $db->exec('PRAGMA busy_timeout=5000');
    $db->exec('CREATE TABLE IF NOT EXISTS submissions (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, respondent TEXT, payload TEXT NOT NULL, source_ip_hash TEXT NOT NULL)');
    $db->exec('CREATE INDEX IF NOT EXISTS submissions_created ON submissions (created_at DESC)');
} catch (Throwable $e) { respond(503, ['error'=>'Database not available']); }
$method = $_SERVER['REQUEST_METHOD'] ?? '';
if ($method === 'POST') {
    if ($origin !== $allowed) respond(403, ['error'=>'Origin not allowed']);
    if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 262144) respond(413, ['error'=>'Response too large']);
    $raw = file_get_contents('php://input', false, null, 0, 262145);
    if ($raw === false || strlen($raw) > 262144) respond(413, ['error'=>'Response too large']);
    $data = json_decode($raw, true);
    if (!is_array($data) || ($data['schema'] ?? null) !== 'adam-sportswear-discovery-v1' || !is_array($data['answers'] ?? null)) respond(422, ['error'=>'Invalid questionnaire payload']);
    if (!empty($data['website'])) respond(422, ['error'=>'Invalid submission']);
    if (count($data['answers']) > 150) respond(422, ['error'=>'Too many answers']);
    foreach ($data['answers'] as $k=>$v) if (!preg_match('/^\d{1,2}-\d{1,2}$/', (string)$k) || !is_string($v) || strlen($v) > 12000) respond(422, ['error'=>'Invalid answer']);
    foreach (['respondent','responseDate','general','dependencies'] as $k) if (isset($data[$k]) && (!is_string($data[$k]) || strlen($data[$k]) > 12000)) respond(422, ['error'=>'Invalid field']);
    $ipHash = hash_hmac('sha256', $_SERVER['REMOTE_ADDR'] ?? 'unknown', getenv('ADAM_IP_SALT') ?: 'configure-independent-random-salt');
    $since = gmdate('Y-m-d\TH:i:s\Z', time()-3600);
    $stmt = $db->prepare('SELECT COUNT(*) FROM submissions WHERE source_ip_hash = :ip AND created_at > :since');
    $stmt->execute([':ip'=>$ipHash, ':since'=>$since]);
    if ((int)$stmt->fetchColumn() >= 8) respond(429, ['error'=>'Submission limit reached; try again later']);
    $id = bin2hex(random_bytes(12));
    $now = gmdate('Y-m-d\TH:i:s\Z');
    // Do not store the unnecessary echoed questionnaire question definitions.
    unset($data['sections'], $data['website']);
    $stmt = $db->prepare('INSERT INTO submissions(id,created_at,respondent,payload,source_ip_hash) VALUES(:id,:created,:respondent,:payload,:ip)');
    $stmt->execute([':id'=>$id, ':created'=>$now, ':respondent'=>substr((string)($data['respondent'] ?? ''),0,250), ':payload'=>json_encode($data, JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE), ':ip'=>$ipHash]);
    respond(201, ['saved'=>true, 'submission_id'=>$id, 'saved_at'=>$now]);
}
if ($method === 'GET') {
    $token = getenv('ADAM_ADMIN_TOKEN');
    $auth = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
    if (!$token || strlen($token) < 32 || !hash_equals('Bearer ' . $token, $auth)) respond(401, ['error'=>'Unauthorized']);
    $id = $_GET['id'] ?? '';
    if ($id !== '') {
        if (!preg_match('/^[a-f0-9]{24}$/', $id)) respond(400, ['error'=>'Invalid id']);
        $stmt=$db->prepare('SELECT id,created_at,respondent,payload FROM submissions WHERE id = ?');$stmt->execute([$id]);$row=$stmt->fetch(PDO::FETCH_ASSOC);
        if (!$row) respond(404, ['error'=>'Not found']);
        respond(200,['submission'=>['id'=>$row['id'],'created_at'=>$row['created_at'],'respondent'=>$row['respondent'],'answers'=>json_decode($row['payload'], true)]]);
    }
    $rows=$db->query('SELECT id,created_at,respondent FROM submissions ORDER BY created_at DESC LIMIT 500')->fetchAll(PDO::FETCH_ASSOC);
    respond(200,['submissions'=>$rows]);
}
respond(405,['error'=>'Method not allowed']);
