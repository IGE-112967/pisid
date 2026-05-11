<?php
session_start();

if (!isset($_SESSION['email'])) {
    header("Location: login.php");
    exit;
}

if (!isset($_GET['jogo_id'])) {
    header("Location: dashboard.php");
    exit;
}

$jogoId = intval($_GET['jogo_id']);

require_once 'config.php';

try {
    $pdo = new PDO("mysql:host=$DB_SERVER;dbname=$DB_NAME;charset=utf8mb4", $DB_USER_APP, $DB_PASSWORD_APP);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    $stmt = $pdo->prepare("CALL Iniciar_Jogo(?, @estado_ok)");
    $stmt->execute([$jogoId]);
    $stmt->closeCursor();

    $result = $pdo->query("SELECT @estado_ok AS permitido")->fetch(PDO::FETCH_ASSOC);

    if ($result && $result['permitido']) {
        $_SESSION['jogo_a_jogar'] = $jogoId;

        $python = "C:\\Users\\gonca\\AppData\\Local\\Programs\\Python\\Python312\\python.exe";

        $scripts = [
            //"C:\\Users\\gonca\\Pisid-2024-2025\\PC1\\ScriptsJogo.py"
            //"C:\\Users\\gonca\\Pisid-2024-2025\\PC1\\S3\\S3_Main.py"
        ];

        foreach ($scripts as $script) {
            $scriptDir = dirname($script);
            $scriptFile = basename($script);

            $cmd = "start cmd /k \"cd /d $scriptDir && $python $scriptFile\"";
            pclose(popen($cmd, "r"));
        }

        header("Location: dashboard.php");
        exit;
    } else {
        echo "Este jogo não pode ser iniciado, pois não está no estado correto.";
    }

} catch (PDOException $e) {
    echo "Erro: " . $e->getMessage();
}
?>
