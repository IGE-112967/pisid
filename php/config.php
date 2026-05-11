<?php
function getConnection() {

    $DB_SERVER = "localhost";
    $DB_NAME   = "marsami";
    $DB_USER   = "root";
    $DB_PASSWORD = "";
    $CHARSET   = "utf8mb4";

    $dsn = "mysql:host=$DB_SERVER;dbname=$DB_NAME;charset=$CHARSET";

    $options = [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ];

    try {
        return new PDO($dsn, $DB_USER, $DB_PASSWORD, $options);
    } catch (PDOException $e) {
        die("Erro de ligação à base de dados: " . $e->getMessage());
    }
}
?>