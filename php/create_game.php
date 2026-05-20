<?php
session_start();

if (!isset($_SESSION['email'])) {
    header("Location: login.php");
    exit;
}

require_once 'config.php';

mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);

$conn = new mysqli($DB_SERVER, $DB_USER_APP, $DB_PASSWORD_APP, $DB_NAME);

if ($conn->connect_error) {
    die("Erro de ligação: " . $conn->connect_error);
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (isset($_POST['descricao']) && !empty(trim($_POST['descricao']))) {
        $descricao = trim($_POST['descricao']);
        $jogador = $_SESSION['email'];

        try {
            $stmt = $conn->prepare("CALL CriarJogo(?, ?)");
            $stmt->bind_param("ss", $descricao, $jogador);
            $stmt->execute();
            $stmt->close();

            header("Location: dashboard.php");
            exit;
        } catch (mysqli_sql_exception $e) {
            if (strpos($e->getMessage(), 'jogo ativo') !== false) {
                $erro = "Já existe um jogo ativo a decorrer.";
            } else {
                $erro = "Erro ao criar o jogo: " . $e->getMessage();
            }
        }
    } else {
        $erro = "A descrição do jogo é obrigatória.";
    }
}

$conn->close();
?>


<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="UTF-8">
  <title>Criar Jogo</title>
  <style>
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: #4169E1;
      color: #000;
    }
    .container {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
    }
    .form-container {
      background: #fff;
      padding: 30px;
      border-radius: 8px;
      box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
      width: 300px;
    }
    .form-container h2 {
      text-align: center;
      margin-bottom: 20px;
    }
    input[type="text"], input[type="submit"] {
      width: 100%;
      padding: 10px;
      margin: 10px 0;
      border-radius: 5px;
      border: 1px solid #ddd;
    }
    input[type="submit"] {
      background-color: #4169E1;
      color: white;
      cursor: pointer;
    }
    .error {
      color: red;
      font-size: 14px;
      text-align: center;
    }
  </style>
</head>
<body>

<div class="container">
    <div class="form-container">
        <h2>Criar Jogo</h2>
        <?php if (isset($erro)): ?>
            <div class="error"><?php echo $erro; ?></div>
        <?php endif; ?>
        <form method="POST" action="">
            <label for="descricao">Descrição do Jogo:</label>
            <input type="text" id="descricao" name="descricao" required>
            <input type="submit" value="Criar Jogo">
        </form>
        <form method="POST" action="dashboard.php">
            <input type="submit" value="Voltar à Dashboard">
        </form>
    </div>
</div>

</body>
</html>
