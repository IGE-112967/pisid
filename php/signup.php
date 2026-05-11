<?php
session_start();

if (isset($_SESSION['email'])) {
    header("Location: dashboard.php");
    exit;
}

require_once 'config.php';
$pdo = getConnection();

$error = "";
$success = "";

if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    $email = $_POST['email'] ?? '';
    $nome = $_POST['nome'] ?? '';
    $telemovel = $_POST['telemovel'] ?? '';
    $password = $_POST['password'] ?? '';

    try {
        // 👉 verificar se já existe email
        $stmt = $pdo->prepare("SELECT Email FROM utilizador WHERE Email = ?");
        $stmt->execute([$email]);

        if ($stmt->fetch()) {
            $error = "Email já está em uso.";
        } else {

            $hash = password_hash($password, PASSWORD_DEFAULT);

            $sql = "INSERT INTO utilizador (Email, Nome, Telemovel, Tipo, Equipa, Password)
                    VALUES (:email, :nome, :telemovel, :tipo, :equipa, :password)";

            $stmt = $pdo->prepare($sql);
            $stmt->execute([
                ':email' => $email,
                ':nome' => $nome,
                ':telemovel' => $telemovel,
                ':tipo' => 'JOG',
                ':equipa' => 6,
                ':password' => $hash
            ]);

            header("Location: login.php");
            exit;
        }

    } catch (PDOException $e) {
        $error = "Erro no servidor.";
    }
}
?>

<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<title>Criar Conta</title>

<style>
body {
    margin: 0;
    font-family: 'Segoe UI', sans-serif;
    background: #0f172a;
    color: #e2e8f0;
}

.container {
    display: flex;
    height: 100vh;
}

/* LEFT */
.left {
    flex: 1;
    background: linear-gradient(135deg, #3b82f6, #1e40af);
    display: flex;
    justify-content: center;
    align-items: center;
    flex-direction: column;
}

.left h1 {
    font-size: 36px;
}

/* RIGHT */
.right {
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
}

/* CARD */
.card {
    background: #1e293b;
    padding: 40px;
    border-radius: 12px;
    width: 350px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
}

.card h2 {
    text-align: center;
    margin-bottom: 20px;
}

/* INPUTS */
input {
    width: 100%;
    padding: 12px;
    margin-bottom: 15px;
    border-radius: 8px;
    border: none;
    background: #334155;
    color: white;
    box-sizing: border-box;
}

/* BUTTON */
button {
    width: 100%;
    padding: 12px;
    border: none;
    border-radius: 8px;
    background: #3b82f6;
    color: white;
    font-weight: bold;
    cursor: pointer;
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

<div class="container">

    <div class="left">
        <h1>🎮 Marsami's Maze</h1>
        <p>Criar Conta</p>
    </div>

    <div class="right">
        <div class="card">

            <h2>Registo</h2>

            <?php if (!empty($error)): ?>
                <div class="error"><?php echo $error; ?></div>
            <?php endif; ?>

            <form method="POST">

                <input type="email" name="email" placeholder="Email" required>
                <input type="text" name="nome" placeholder="Nome" required>
                <input type="text" name="telemovel" placeholder="Telemóvel" required>
                <input type="password" name="password" placeholder="Password" required>

                <button type="submit">Criar Conta</button>

            </form>

            <form action="login.php">
                <button type="submit" class="secondary">Ir para Login</button>
            </form>

        </div>
    </div>

</div>

</body>
</html>