<?php
session_start();

if (!isset($_SESSION['email'])) {
    header("Location: login.php");
    exit;
}

require_once 'config.php';
$pdo = getConnection();

$email = $_SESSION['email'];

// 👉 validar ID
if (!isset($_GET['jogo_id']) || empty($_GET['jogo_id'])) {
    header("Location: dashboard.php");
    exit;
}

$jogo_id = (int) $_GET['jogo_id'];

try {
    // 👉 garantir que o jogo pertence ao user
    $stmt = $pdo->prepare("
        SELECT ID_Simulacao 
        FROM simulacao 
        WHERE ID_Simulacao = ? AND Email = ?
    ");
    $stmt->execute([$jogo_id, $email]);

    $jogo = $stmt->fetch();

    if (!$jogo) {
        // não existe ou não pertence ao user
        header("Location: dashboard.php");
        exit;
    }

    // 👉 apagar simulação
    $delete = $pdo->prepare("
        DELETE FROM simulacao 
        WHERE ID_Simulacao = ?
    ");
    $delete->execute([$jogo_id]);

    // 👉 voltar ao dashboard
    header("Location: dashboard.php");
    exit;

} catch (PDOException $e) {
    die("Erro ao remover simulação.");
}
?>