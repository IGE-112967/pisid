<?php
if (!isset($_GET['jogo_id'])) {
    http_response_code(400);
    echo json_encode(["erro" => "ID do jogo não fornecido"]);
    exit;
}

$jogo_id = intval($_GET['jogo_id']);

require_once 'config.php';

$conn = new mysqli($DB_SERVER, $DB_USER_APP, $DB_PASSWORD_APP, $DB_NAME);

if ($conn->connect_error) {
    http_response_code(500);
    echo json_encode(["erro" => "Erro de ligação à base de dados"]);
    exit;
}

$stmt = $conn->prepare("CALL GetPontuacaoPorJogo(?)");
$stmt->bind_param("i", $jogo_id);
$stmt->execute();
$result = $stmt->get_result();

if ($row = $result->fetch_assoc()) {
    echo json_encode(["pontos" => $row["pontos"]]);
} else {
    http_response_code(404);
    echo json_encode(["erro" => "Jogo não encontrado"]);
}

$stmt->close();
$conn->close();
?>
