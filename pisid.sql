-- phpMyAdmin SQL Dump
-- version 5.2.3
-- https://www.phpmyadmin.net/
--
-- Host: mysql
-- Generation Time: May 06, 2026 at 02:52 PM
-- Server version: 8.0.45
-- PHP Version: 8.3.30

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `pisid`
--

DELIMITER $$
--
-- Procedures
--
CREATE DEFINER=`root`@`%` PROCEDURE `sp_atualizar_estado_movimento` (IN `p_ID_Simulacao` INT, IN `p_SalaOrigem` INT, IN `p_SalaDestino` INT, IN `p_Marsami` INT, IN `p_Status` INT)   BEGIN
    DECLARE v_Paridade VARCHAR(10);
    DECLARE v_SalaAnterior INT DEFAULT NULL;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_SalaAnterior = NULL;

    SET v_Paridade = IF(MOD(p_Marsami, 2) = 0, 'even', 'odd');

    SELECT SalaAtual
    INTO v_SalaAnterior
    FROM estado_marsami
    WHERE ID_Simulacao = p_ID_Simulacao
      AND Marsami = p_Marsami
    LIMIT 1;

    /* Caso 1: largada inicial */
    IF p_SalaOrigem = 0 AND p_SalaDestino > 0 THEN
        IF v_SalaAnterior IS NOT NULL AND v_SalaAnterior > 0 THEN
            CALL sp_incrementar_ocupacao(p_ID_Simulacao, v_SalaAnterior, v_Paridade, -1);
        END IF;

        INSERT INTO estado_marsami (
            ID_Simulacao,
            Marsami,
            SalaAtual,
            Paridade,
            Ativo
        )
        VALUES (p_ID_Simulacao, p_Marsami, p_SalaDestino, v_Paridade, TRUE)
        ON DUPLICATE KEY UPDATE
            SalaAtual = p_SalaDestino,
            Paridade = v_Paridade,
            Ativo = TRUE,
            UltimaAtualizacao = CURRENT_TIMESTAMP;

        CALL sp_incrementar_ocupacao(p_ID_Simulacao, p_SalaDestino, v_Paridade, 1);
        CALL sp_verificar_score(p_ID_Simulacao, p_SalaDestino);

    /* Caso 2: marsami preso/cansado */
    ELSEIF p_SalaOrigem = 0 AND p_SalaDestino = 0 THEN
        IF v_SalaAnterior IS NOT NULL THEN
            UPDATE estado_marsami
            SET Ativo = FALSE,
                UltimaAtualizacao = CURRENT_TIMESTAMP
            WHERE ID_Simulacao = p_ID_Simulacao
              AND Marsami = p_Marsami;

            CALL sp_verificar_score(p_ID_Simulacao, v_SalaAnterior);
        END IF;

    /* Caso 3: movimento normal */
    ELSEIF p_SalaOrigem > 0 AND p_SalaDestino > 0 THEN
        IF v_SalaAnterior IS NULL OR v_SalaAnterior <= 0 THEN
            SET v_SalaAnterior = p_SalaOrigem;
        END IF;

        CALL sp_incrementar_ocupacao(p_ID_Simulacao, v_SalaAnterior, v_Paridade, -1);
        CALL sp_incrementar_ocupacao(p_ID_Simulacao, p_SalaDestino, v_Paridade, 1);

        INSERT INTO estado_marsami (
            ID_Simulacao,
            Marsami,
            SalaAtual,
            Paridade,
            Ativo
        )
        VALUES (p_ID_Simulacao, p_Marsami, p_SalaDestino, v_Paridade, TRUE)
        ON DUPLICATE KEY UPDATE
            SalaAtual = p_SalaDestino,
            Paridade = v_Paridade,
            Ativo = TRUE,
            UltimaAtualizacao = CURRENT_TIMESTAMP;

        CALL sp_verificar_score(p_ID_Simulacao, v_SalaAnterior);
        CALL sp_verificar_score(p_ID_Simulacao, p_SalaDestino);
    END IF;
END$$

CREATE DEFINER=`root`@`%` PROCEDURE `sp_garantir_simulacao_ativa` (IN `p_Player` INT, OUT `p_ID_Simulacao` INT)   BEGIN
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET p_ID_Simulacao = NULL;

    SET p_ID_Simulacao = NULL;

    SELECT ID_Simulacao
    INTO p_ID_Simulacao
    FROM simulacao
    WHERE Player = p_Player
    ORDER BY DataHoraInicio DESC, ID_Simulacao DESC
    LIMIT 1;

    IF p_ID_Simulacao IS NULL THEN
        INSERT INTO simulacao (Descricao, Equipa, Player)
        VALUES ('Simulação criada automaticamente pelo S3', p_Player, p_Player);

        SET p_ID_Simulacao = LAST_INSERT_ID();
    END IF;
END$$

CREATE DEFINER=`root`@`%` PROCEDURE `sp_incrementar_ocupacao` (IN `p_ID_Simulacao` INT, IN `p_Sala` INT, IN `p_Paridade` VARCHAR(10), IN `p_Delta` INT)   BEGIN
    IF p_Sala IS NOT NULL AND p_Sala > 0 THEN
        INSERT INTO ocupacao_labirinto (
            ID_Simulacao,
            Sala,
            NumeroMarsamisOdd,
            NumeroMarsamisEven,
            TriggerCount
        )
        VALUES (p_ID_Simulacao, p_Sala, 0, 0, 0)
        ON DUPLICATE KEY UPDATE
            UltimaAtualizacao = CURRENT_TIMESTAMP;

        IF p_Paridade = 'odd' THEN
            UPDATE ocupacao_labirinto
            SET NumeroMarsamisOdd = GREATEST(0, NumeroMarsamisOdd + p_Delta),
                UltimaAtualizacao = CURRENT_TIMESTAMP
            WHERE ID_Simulacao = p_ID_Simulacao
              AND Sala = p_Sala;
        ELSE
            UPDATE ocupacao_labirinto
            SET NumeroMarsamisEven = GREATEST(0, NumeroMarsamisEven + p_Delta),
                UltimaAtualizacao = CURRENT_TIMESTAMP
            WHERE ID_Simulacao = p_ID_Simulacao
              AND Sala = p_Sala;
        END IF;
    END IF;
END$$

CREATE DEFINER=`root`@`%` PROCEDURE `sp_inserir_medicao_passagem` (IN `p_Player` INT, IN `p_Hora` TIMESTAMP, IN `p_SalaOrigem` INT, IN `p_SalaDestino` INT, IN `p_Marsami` INT, IN `p_Status` INT)   BEGIN
    DECLARE v_ID_Simulacao INT;

    CALL sp_garantir_simulacao_ativa(p_Player, v_ID_Simulacao);

    INSERT INTO medicoes_passagens (
        Hora,
        SalaOrigem,
        SalaDestino,
        Marsami,
        Status,
        ID_Simulacao
    )
    VALUES (
        COALESCE(p_Hora, CURRENT_TIMESTAMP),
        p_SalaOrigem,
        p_SalaDestino,
        p_Marsami,
        p_Status,
        v_ID_Simulacao
    );
END$$

CREATE DEFINER=`root`@`%` PROCEDURE `sp_inserir_som` (IN `p_Player` INT, IN `p_Hora` TIMESTAMP, IN `p_Som` DECIMAL(6,2))   BEGIN
    DECLARE v_ID_Simulacao INT;

    CALL sp_garantir_simulacao_ativa(p_Player, v_ID_Simulacao);

    INSERT INTO som (Hora, Som, ID_Simulacao)
    VALUES (COALESCE(p_Hora, CURRENT_TIMESTAMP), p_Som, v_ID_Simulacao);
END$$

CREATE DEFINER=`root`@`%` PROCEDURE `sp_inserir_temperatura` (IN `p_Player` INT, IN `p_Hora` TIMESTAMP, IN `p_Temperatura` DECIMAL(5,2))   BEGIN
    DECLARE v_ID_Simulacao INT;

    CALL sp_garantir_simulacao_ativa(p_Player, v_ID_Simulacao);

    INSERT INTO temperatura (Hora, Temperatura, ID_Simulacao)
    VALUES (COALESCE(p_Hora, CURRENT_TIMESTAMP), p_Temperatura, v_ID_Simulacao);
END$$

CREATE DEFINER=`root`@`%` PROCEDURE `sp_verificar_score` (IN `p_ID_Simulacao` INT, IN `p_Sala` INT)   BEGIN
    DECLARE v_Odd INT DEFAULT 0;
    DECLARE v_Even INT DEFAULT 0;
    DECLARE v_TriggerCount INT DEFAULT 0;
    DECLARE v_Existe INT DEFAULT 0;

    IF p_Sala IS NULL OR p_Sala <= 0 THEN
        SET v_Existe = 1;
    ELSE
        SELECT NumeroMarsamisOdd, NumeroMarsamisEven, TriggerCount
        INTO v_Odd, v_Even, v_TriggerCount
        FROM ocupacao_labirinto
        WHERE ID_Simulacao = p_ID_Simulacao
          AND Sala = p_Sala;

        IF v_Odd > 0 AND v_Odd = v_Even AND v_TriggerCount < 3 THEN
            SELECT COUNT(*)
            INTO v_Existe
            FROM score_eventos
            WHERE ID_Simulacao = p_ID_Simulacao
              AND Sala = p_Sala
              AND NumeroOdd = v_Odd
              AND NumeroEven = v_Even;

            IF v_Existe = 0 THEN
                INSERT INTO score_eventos (
                    ID_Simulacao,
                    Sala,
                    NumeroOdd,
                    NumeroEven
                )
                VALUES (p_ID_Simulacao, p_Sala, v_Odd, v_Even);

                UPDATE ocupacao_labirinto
                SET TriggerCount = TriggerCount + 1,
                    UltimaAtualizacao = CURRENT_TIMESTAMP
                WHERE ID_Simulacao = p_ID_Simulacao
                  AND Sala = p_Sala;

                UPDATE simulacao
                SET Pontuacao = Pontuacao + 1
                WHERE ID_Simulacao = p_ID_Simulacao;
            END IF;
        END IF;
    END IF;
END$$

DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `estado_marsami`
--

CREATE TABLE `estado_marsami` (
  `ID_Simulacao` int NOT NULL,
  `Marsami` int NOT NULL,
  `SalaAtual` int DEFAULT NULL,
  `Paridade` varchar(10) NOT NULL,
  `Ativo` tinyint(1) DEFAULT '1',
  `UltimaAtualizacao` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `medicoes_passagens`
--

CREATE TABLE `medicoes_passagens` (
  `ID_Medicao` int NOT NULL,
  `Hora` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `SalaOrigem` int DEFAULT NULL,
  `SalaDestino` int DEFAULT NULL,
  `Marsami` int NOT NULL,
  `Status` int NOT NULL,
  `ID_Simulacao` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Triggers `medicoes_passagens`
--
DELIMITER $$
CREATE TRIGGER `trg_medicoes_passagens_ai` AFTER INSERT ON `medicoes_passagens` FOR EACH ROW BEGIN
    CALL sp_atualizar_estado_movimento(
        NEW.ID_Simulacao,
        NEW.SalaOrigem,
        NEW.SalaDestino,
        NEW.Marsami,
        NEW.Status
    );
END
$$
DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `mensagens`
--

CREATE TABLE `mensagens` (
  `ID` int NOT NULL,
  `Hora` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `Sala` int DEFAULT NULL,
  `Sensor` varchar(20) DEFAULT NULL,
  `Leitura` decimal(6,2) DEFAULT NULL,
  `TipoAlerta` varchar(50) DEFAULT NULL,
  `Msg` varchar(100) DEFAULT NULL,
  `HoraEscrita` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `ID_Simulacao` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `ocupacao_labirinto`
--

CREATE TABLE `ocupacao_labirinto` (
  `ID_Simulacao` int NOT NULL,
  `Sala` int NOT NULL,
  `NumeroMarsamisOdd` int DEFAULT '0',
  `NumeroMarsamisEven` int DEFAULT '0',
  `TriggerCount` int DEFAULT '0',
  `UltimaAtualizacao` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `score_eventos`
--

CREATE TABLE `score_eventos` (
  `ID_Score` int NOT NULL,
  `ID_Simulacao` int NOT NULL,
  `Sala` int NOT NULL,
  `NumeroOdd` int NOT NULL,
  `NumeroEven` int NOT NULL,
  `Hora` timestamp NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `simulacao`
--

CREATE TABLE `simulacao` (
  `ID_Simulacao` int NOT NULL,
  `Descricao` text,
  `Equipa` int NOT NULL,
  `Player` int NOT NULL,
  `DataHoraInicio` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `Pontuacao` decimal(6,2) DEFAULT '0.00',
  `Email` varchar(50) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `som`
--

CREATE TABLE `som` (
  `ID_Som` int NOT NULL,
  `Hora` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `Som` decimal(6,2) NOT NULL,
  `ID_Simulacao` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Triggers `som`
--
DELIMITER $$
CREATE TRIGGER `trg_som_alerta_ai` AFTER INSERT ON `som` FOR EACH ROW BEGIN
    IF NEW.Som >= 120 THEN

        IF NOT EXISTS (
            SELECT 1
            FROM mensagens
            WHERE ID_Simulacao = NEW.ID_Simulacao
              AND TipoAlerta = 'ALERTA_SOM'
              AND HoraEscrita >= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 30 SECOND)
        ) THEN

            INSERT INTO mensagens (
                Hora,
                Sala,
                Sensor,
                Leitura,
                TipoAlerta,
                Msg,
                ID_Simulacao
            )
            VALUES (
                NEW.Hora,
                NULL,
                '2',
                NEW.Som,
                'ALERTA_SOM',
                CONCAT('Aviso: nível de ruído elevado: ', NEW.Som),
                NEW.ID_Simulacao
            );

        END IF;

    END IF;
END
$$
DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `temperatura`
--

CREATE TABLE `temperatura` (
  `ID_Temperatura` int NOT NULL,
  `Hora` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `Temperatura` decimal(5,2) NOT NULL,
  `ID_Simulacao` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Triggers `temperatura`
--
DELIMITER $$
CREATE TRIGGER `trg_temperatura_alerta_ai` AFTER INSERT ON `temperatura` FOR EACH ROW BEGIN
    IF NEW.Temperatura >= 60 OR NEW.Temperatura <= 0 THEN

        IF NOT EXISTS (
            SELECT 1
            FROM mensagens
            WHERE ID_Simulacao = NEW.ID_Simulacao
              AND TipoAlerta = 'ALERTA_TEMPERATURA'
              AND HoraEscrita >= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 30 SECOND)
        ) THEN

            INSERT INTO mensagens (
                Hora,
                Sala,
                Sensor,
                Leitura,
                TipoAlerta,
                Msg,
                ID_Simulacao
            )
            VALUES (
                NEW.Hora,
                NULL,
                '1',
                NEW.Temperatura,
                'ALERTA_TEMPERATURA',
                CONCAT('Aviso: temperatura fora do intervalo normal: ', NEW.Temperatura),
                NEW.ID_Simulacao
            );

        END IF;

    END IF;
END
$$
DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `utilizador`
--

CREATE TABLE `utilizador` (
  `Email` varchar(50) NOT NULL,
  `Nome` varchar(100) NOT NULL,
  `Telemovel` varchar(12) DEFAULT NULL,
  `Tipo` varchar(20) DEFAULT NULL,
  `DataNascimento` date DEFAULT NULL,
  `Equipa` int DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `estado_marsami`
--
ALTER TABLE `estado_marsami`
  ADD PRIMARY KEY (`ID_Simulacao`,`Marsami`);

--
-- Indexes for table `medicoes_passagens`
--
ALTER TABLE `medicoes_passagens`
  ADD PRIMARY KEY (`ID_Medicao`),
  ADD KEY `ID_Simulacao` (`ID_Simulacao`);

--
-- Indexes for table `mensagens`
--
ALTER TABLE `mensagens`
  ADD PRIMARY KEY (`ID`),
  ADD KEY `ID_Simulacao` (`ID_Simulacao`);

--
-- Indexes for table `ocupacao_labirinto`
--
ALTER TABLE `ocupacao_labirinto`
  ADD PRIMARY KEY (`ID_Simulacao`,`Sala`);

--
-- Indexes for table `score_eventos`
--
ALTER TABLE `score_eventos`
  ADD PRIMARY KEY (`ID_Score`),
  ADD KEY `ID_Simulacao` (`ID_Simulacao`);

--
-- Indexes for table `simulacao`
--
ALTER TABLE `simulacao`
  ADD PRIMARY KEY (`ID_Simulacao`),
  ADD KEY `Email` (`Email`);

--
-- Indexes for table `som`
--
ALTER TABLE `som`
  ADD PRIMARY KEY (`ID_Som`),
  ADD KEY `ID_Simulacao` (`ID_Simulacao`);

--
-- Indexes for table `temperatura`
--
ALTER TABLE `temperatura`
  ADD PRIMARY KEY (`ID_Temperatura`),
  ADD KEY `ID_Simulacao` (`ID_Simulacao`);

--
-- Indexes for table `utilizador`
--
ALTER TABLE `utilizador`
  ADD PRIMARY KEY (`Email`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `medicoes_passagens`
--
ALTER TABLE `medicoes_passagens`
  MODIFY `ID_Medicao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `mensagens`
--
ALTER TABLE `mensagens`
  MODIFY `ID` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `score_eventos`
--
ALTER TABLE `score_eventos`
  MODIFY `ID_Score` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `simulacao`
--
ALTER TABLE `simulacao`
  MODIFY `ID_Simulacao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `som`
--
ALTER TABLE `som`
  MODIFY `ID_Som` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `temperatura`
--
ALTER TABLE `temperatura`
  MODIFY `ID_Temperatura` int NOT NULL AUTO_INCREMENT;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `estado_marsami`
--
ALTER TABLE `estado_marsami`
  ADD CONSTRAINT `estado_marsami_ibfk_1` FOREIGN KEY (`ID_Simulacao`) REFERENCES `simulacao` (`ID_Simulacao`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `medicoes_passagens`
--
ALTER TABLE `medicoes_passagens`
  ADD CONSTRAINT `medicoes_passagens_ibfk_1` FOREIGN KEY (`ID_Simulacao`) REFERENCES `simulacao` (`ID_Simulacao`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `mensagens`
--
ALTER TABLE `mensagens`
  ADD CONSTRAINT `mensagens_ibfk_1` FOREIGN KEY (`ID_Simulacao`) REFERENCES `simulacao` (`ID_Simulacao`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `ocupacao_labirinto`
--
ALTER TABLE `ocupacao_labirinto`
  ADD CONSTRAINT `ocupacao_labirinto_ibfk_1` FOREIGN KEY (`ID_Simulacao`) REFERENCES `simulacao` (`ID_Simulacao`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `score_eventos`
--
ALTER TABLE `score_eventos`
  ADD CONSTRAINT `score_eventos_ibfk_1` FOREIGN KEY (`ID_Simulacao`) REFERENCES `simulacao` (`ID_Simulacao`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `simulacao`
--
ALTER TABLE `simulacao`
  ADD CONSTRAINT `simulacao_ibfk_1` FOREIGN KEY (`Email`) REFERENCES `utilizador` (`Email`) ON DELETE SET NULL ON UPDATE CASCADE;

--
-- Constraints for table `som`
--
ALTER TABLE `som`
  ADD CONSTRAINT `som_ibfk_1` FOREIGN KEY (`ID_Simulacao`) REFERENCES `simulacao` (`ID_Simulacao`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `temperatura`
--
ALTER TABLE `temperatura`
  ADD CONSTRAINT `temperatura_ibfk_1` FOREIGN KEY (`ID_Simulacao`) REFERENCES `simulacao` (`ID_Simulacao`) ON DELETE CASCADE ON UPDATE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
