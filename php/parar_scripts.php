<?php
session_start();
if (!isset($_SESSION['email'])) {
    header("Location: login.php");
    exit;
}

exec("taskkill /F /IM python.exe /T");

header("Location: dashboard.php");
exit;
?>
