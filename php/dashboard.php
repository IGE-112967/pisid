<?php
session_start();

if (!isset($_SESSION['email'])) {
    header("Location: login.php");
    exit;
}

require_once 'config.php';
$pdo = getConnection();

$nome = $_SESSION['nome'];
$email = $_SESSION['email'];

try {
    // 👉 buscar jogos do utilizador
    $stmt = $pdo->prepare("
        SELECT ID_Simulacao, Descricao, DataHoraInicio, Pontuacao
        FROM simulacao
        WHERE Email = ?
        ORDER BY DataHoraInicio DESC
    ");

    $stmt->execute([$email]);
    $jogos = $stmt->fetchAll();

} catch (PDOException $e) {
    die("Erro: " . $e->getMessage());
}
?>

<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<title>Dashboard - Marsami</title>

<style>
body {
    margin: 0;
    font-family: 'Segoe UI', sans-serif;
    background: #0f172a;
    color: #e2e8f0;
}

/* LAYOUT */
.container {
    display: flex;
    min-height: 100vh;
}

/* SIDEBAR */
.sidebar {
    width: 250px;
    background: #1e293b;
    padding: 20px;
}

.sidebar h3 {
    text-align: center;
}

.sidebar button {
    width: 100%;
    padding: 10px;
    margin-top: 10px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    background: #3b82f6;
    color: white;
}

.sidebar .danger {
    background: #ef4444;
}

/* CONTENT */
.content {
    flex: 1;
    padding: 30px;
}

/* CARD JOGO */
.card {
    background: #1e293b;
    padding: 20px;
    border-radius: 12px;
    margin-bottom: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.info {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.actions {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.actions button {
    padding: 8px 12px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    color: white;
}

.edit { background: #3b82f6; }
.delete { background: #ef4444; }
.play { background: #22c55e; }

.title {
    font-size: 22px;
    margin-bottom: 20px;
}
</style>
</head>

<body>

<div class="container">

    <!-- SIDEBAR -->
    <div class="sidebar">
        <h3>👤 <?php echo htmlspecialchars($nome); ?></h3>

        <button onclick="location.href='edit_profile.php'">Editar Perfil</button>
        <button onclick="location.href='create_game.php'">Criar Simulação</button>

        <form action="parar_scripts.php" method="POST">
            <button class="danger" type="submit">Parar Simulação</button>
        </form>

        <button onclick="location.href='logout.php'">Logout</button>
    </div>

    <!-- CONTENT -->
    <div class="content">

        <div class="title">🎮 As tuas Simulações</div>

        <?php if (empty($jogos)): ?>
            <p>Não tens simulações criadas.</p>
        <?php endif; ?>

        <?php foreach ($jogos as $jogo): ?>

        <div class="card">

            <div class="info">
                <strong>#<?php echo $jogo['ID_Simulacao']; ?></strong>

                <span><?php echo htmlspecialchars($jogo['Descricao']); ?></span>

                <small>
                    Criado em: <?php echo date("d/m/Y H:i", strtotime($jogo['DataHoraInicio'])); ?>
                </small>

                <small>
                    Pontos: <?php echo $jogo['Pontuacao']; ?>
                </small>
            </div>

            <div class="actions">

                <form method="GET" action="executar_jogo.php">
                    <input type="hidden" name="jogo_id" value="<?php echo $jogo['ID_Simulacao']; ?>">
                    <button class="play">Jogar</button>
                </form>

                <form method="GET" action="alterar_jogo.php">
                    <input type="hidden" name="jogo_id" value="<?php echo $jogo['ID_Simulacao']; ?>">
                    <button class="edit">Editar</button>
                </form>

                <form method="GET" action="remover_jogo.php">
                    <input type="hidden" name="jogo_id" value="<?php echo $jogo['ID_Simulacao']; ?>">
                    <button class="delete">Remover</button>
                </form>

            </div>

        </div>

        <?php endforeach; ?>

    </div>

</div>

</body>
</html>