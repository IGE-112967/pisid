<?php
session_start();

if (!isset($_SESSION['email'])) {
    header("Location: login.php");
    exit;
}

$msg = "";
$nome = "";
$telemovel = "";

require_once 'config.php';

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    $conn = new mysqli($DB_SERVER, $DB_USER_APP, $DB_PASSWORD_APP, $DB_NAME);

    if ($conn->connect_error) {
        die("Erro de ligação: " . $conn->connect_error);
    }

    $email = $_SESSION['email'];
    $nome = $_POST['nome'];
    $current_password = $_POST['current_password'];
    $new_password = isset($_POST['new_password']) ? $_POST['new_password'] : null;

    $sql = "CALL Atualizar_Informacoes_Utilizador(?, ?, ?, ?, ?)";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("sssss", $email, $nome, $telemovel, $current_password, $new_password);

    if ($stmt->execute()) {
        header("Location: dashboard.php");
        exit;
    } else {
        $msg = "Erro ao atualizar perfil: " . $stmt->error;
    }

    $stmt->close();
    $conn->close();
} else {
    $conn = new mysqli($DB_SERVER, $DB_USER_APP, $DB_PASSWORD_APP, $DB_NAME);

    if ($conn->connect_error) {
        die("Erro de ligação: " . $conn->connect_error);
    }

    $email = $_SESSION['email'];
    $sql = "CALL GetUtilizadorInfo(?)";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("s", $email);
    $stmt->execute();
    $result = $stmt->get_result();

    if ($result && $result->num_rows > 0) {
        $user = $result->fetch_assoc();
        $nome = $user['Nome'];
        $telemovel = $user['Telemovel'];
    }
    $stmt->close();
    $conn->close();
}
?>


<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="UTF-8">
  <title>Editar Perfil</title>
  <style>
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: #1f1f1f;
      color: #333;
    }
    .container {
      display: flex;
      height: 100vh;
    }
    .left-panel {
      flex: 1;
      background: #4169E1;
      color: white;
      display: flex;
      justify-content: center;
      align-items: center;
      flex-direction: column;
    }
    .right-panel {
      flex: 1;
      background: white;
      display: flex;
      justify-content: center;
      align-items: center;
    }
    .form-box {
      width: 300px;
    }
    input {
      width: 100%;
      padding: 10px;
      margin: 10px 0;
    }
    button {
      background: #4169E1;
      color: white;
      border: none;
      padding: 10px;
      width: 100%;
      cursor: pointer;
    }
    .message {
      margin-bottom: 15px;
      color: green;
      font-weight: bold;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="left-panel">
      <h2>Editar Perfil</h2>
    </div>
    <div class="right-panel">
      <div class="form-box">
        <?php if (!empty($msg)) echo "<div class='message'>$msg</div>"; ?>
        <form method="POST" action="edit_profile.php">
            <label for="email">Email (não editável)</label>
            <input type="email" id="email" name="email" value="<?php echo htmlspecialchars($_SESSION['email']); ?>" readonly required>

            <label for="nome">Nome</label>
            <input type="text" id="nome" name="nome" value="<?php echo htmlspecialchars($nome); ?>" required> <!-- Agora o campo de nome começa com o valor do banco de dados -->

            <label for="telemovel">Telemóvel (não editável)</label>
            <input type="text" id="telemovel" name="telemovel" value="<?php echo htmlspecialchars($telemovel); ?>" readonly required>

            <label for="current_password">Password Atual</label>
            <input type="password" id="current_password" name="current_password" required>

            <label for="new_password">Nova Password</label>
            <input type="password" id="new_password" name="new_password">

            <button type="submit">Atualizar Perfil</button>
        </form>

        <form action="dashboard.php">
            <button type="submit" style="margin-top: 10px;">Voltar à Dashboard</button>
        </form>
      </div>
    </div>
  </div>
</body>
</html>
