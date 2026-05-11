<?php
session_start();

if (!isset($_SESSION['email'])) {
    header("Location: login.php");
    exit;
}

require_once 'config.php';
$pdo = getConnection();

$erro = "";
$jogo_id = "";
$descricao = "";
$player = "";

// 👉 Atualizar jogo
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $jogo_id = $_POST['jogo_id'];
    $descricao = $_POST['descricao'];
    $player = $_POST['player'];

    try {
        $sql = "UPDATE simulacao 
                SET Descricao = :descricao, Player = :player 
                WHERE ID_Simulacao = :id";

        $stmt = $pdo->prepare($sql);
        $stmt->execute([
            ':descricao' => $descricao,
            ':player' => $player,
            ':id' => $jogo_id
        ]);

        header("Location: dashboard.php");
        exit;

    } catch (PDOException $e) {
        $erro = "Erro: " . $e->getMessage();
    }
}

// 👉 Buscar dados do jogo
if (isset($_GET['jogo_id'])) {
    $jogo_id = $_GET['jogo_id'];

    $stmt = $pdo->prepare("SELECT Descricao, Player FROM simulacao WHERE ID_Simulacao = ?");
    $stmt->execute([$jogo_id]);

    $jogo = $stmt->fetch();

    if ($jogo) {
        $descricao = $jogo['Descricao'];
        $player = $jogo['Player'];
    } else {
        $erro = "Jogo não encontrado.";
    }
}
?>

<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<title>Editar Simulação</title>

<style>
body {
    margin: 0;
    font-family: 'Segoe UI', sans-serif;
    background: #0f172a;
    color: #e2e8f0;
}

.header {
    background: #1e293b;
    padding: 15px 30px;
    font-size: 20px;
    font-weight: bold;
}

.container {
    display: flex;
    justify-content: center;
    align-items: center;
    height: calc(100vh - 60px);
}

.card {
    background: #1e293b;
    padding: 40px;
    border-radius: 12px;
    width: 400px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
}

.card h2 {
    margin-bottom: 20px;
    text-align: center;
}

input, textarea {
    width: 100%;
    padding: 12px;
    margin-bottom: 15px;
    border-radius: 8px;
    border: none;
    outline: none;
    background: #334155;
    color: white;
    box-sizing: border-box;
}

textarea {
    resize: none;
    height: 100px;
}

button {
    width: 100%;
    padding: 12px;
    border: none;
    border-radius: 8px;
    background: #3b82f6;
    color: white;
    font-weight: bold;
    cursor: pointer;
    transition: 0.2s;
}

button:hover {
    background: #2563eb;
}

.secondary {
    background: #64748b;
    margin-top: 10px;
}

.error {
    background: #7f1d1d;
    padding: 10px;
    border-radius: 6px;
    margin-bottom: 15px;
    text-align: center;
}
</style>
</head>

<body>

<div class="header">
    🎮 Sistema de Simulações
</div>

<div class="container">
    <div class="card">

        <h2>Editar Simulação</h2>

        <?php if (!empty($erro)): ?>
            <div class="error"><?php echo $erro; ?></div>
        <?php endif; ?>

        <form method="POST">
            <input type="hidden" name="jogo_id" value="<?php echo htmlspecialchars($jogo_id); ?>">

            <label>Descrição</label>
            <textarea name="descricao" required><?php echo htmlspecialchars($descricao); ?></textarea>

            <label>Player</label>
            <input type="number" name="player" required value="<?php echo htmlspecialchars($player); ?>">

            <button type="submit">Guardar Alterações</button>
        </form>

        <form action="dashboard.php">
            <button type="submit" class="secondary">Voltar</button>
        </form>

    </div>
</div>

</body>
</html>