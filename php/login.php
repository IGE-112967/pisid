<?php
session_start();

if (isset($_SESSION['email'])) {
    header("Location: dashboard.php");
    exit;
}

require_once 'config.php';
$pdo = getConnection();

$error_message = "";

if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    $email = $_POST['email'] ?? '';
    $senha = $_POST['password'] ?? '';

    try {
        $stmt = $pdo->prepare("SELECT Email, Nome, Password FROM utilizador WHERE Email = ?");
        $stmt->execute([$email]);

        $user = $stmt->fetch();

        if ($user) {
            if (password_verify($senha, $user['Password'])) {
                $_SESSION['email'] = $user['Email'];
                $_SESSION['nome'] = $user['Nome'];

                header("Location: dashboard.php");
                exit;
            } else {
                $error_message = "Password incorreta.";
            }
        } else {
            $error_message = "Email não encontrado.";
        }

    } catch (PDOException $e) {
        $error_message = "Erro no servidor.";
    }
}
?>

<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<title>Login - Sistema</title>

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

/* Lado esquerdo */
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
    margin-bottom: 10px;
}

.left p {
    opacity: 0.8;
}

/* Lado direito */
.right {
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
}

/* Card */
.card {
    background: #1e293b;
    padding: 40px;
    border-radius: 12px;
    width: 350px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
}

.card h2 {
    margin-bottom: 20px;
    text-align: center;
}

/* Inputs */
.form-input {
    width: 100%;
    padding: 12px;
    margin-bottom: 15px;
    border-radius: 8px;
    border: none;
    background: #334155;
    color: white;
    box-sizing: border-box;
}

input:focus {
    outline: 2px solid #3b82f6;
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

<div class="container">

    <div class="left">
        <h1>🎮 Marsami's Maze</h1>
        <p>Simulações de Labirintos de Marsamis</p>
    </div>

    <div class="right">
        <div class="card">

            <h2>Login</h2>

            <?php if (!empty($error_message)): ?>
                <div class="error"><?php echo $error_message; ?></div>
            <?php endif; ?>

            <form method="POST">

                <input class="form-input" type="email" name="email" placeholder="Email" required>
                <input class="form-input" type="password" name="password" placeholder="Password" required>
                <button type="submit">Entrar</button>

            </form>

            <form action="signup.php">
                <button type="submit" class="secondary">Criar Conta</button>
            </form>

        </div>
    </div>

</div>

</body>
</html>