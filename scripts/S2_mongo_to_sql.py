import json
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt
from bson import ObjectId
from pymongo import MongoClient

# =========================================================
# CONFIGURAÇÕES
# =========================================================
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883

# Tópico intermédio usado pelo S3 para inserir no MySQL.
MQTT_TOPIC_TO_SQL = "pisid_to_sql_34"

MONGO_URI = "mongodb://localhost:27017/?directConnection=true"
MONGO_DB = "pisid"

# Granularidade de segundo, conforme definido para a migração incremental.
INTERVALO_SEGUNDOS = 1
JANELA_DUPLICADOS_SEGUNDOS = 10

# Outliers por variação face à última leitura válida do mesmo Player.
# O valor atual tem de ficar dentro do intervalo:
# último_valor - 150% até último_valor + 150%.
# Exemplo: último som = 20 -> intervalo aceite: -10 a 50.
PERCENTAGEM_VARIACAO_OUTLIER = 1.5

# =========================================================
# LIGAÇÃO AO MONGO
# =========================================================
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

# Na implementação final o MongoDB fica apenas com as coleções de receção,
# validação e sinalização. O estado do labirinto passa para o MySQL.
col_movement = db["movement"]
col_sound = db["sound"]
col_temperature = db["temperature"]
col_flagged = db["flagged"]

# Índices úteis para procurar documentos por processar e controlar duplicados.
col_movement.create_index("ProcessedAt")
col_sound.create_index("ProcessedAt")
col_temperature.create_index("ProcessedAt")
col_movement.create_index([
    ("Player", 1),
    ("Marsami", 1),
    ("RoomOrigin", 1),
    ("RoomDestiny", 1),
    ("Status", 1),
    ("ProcessedAt", 1),
])
col_sound.create_index([
    ("Player", 1),
    ("Hour", 1),
    ("Sound", 1),
    ("ProcessedAt", 1),
])
col_temperature.create_index([
    ("Player", 1),
    ("Hour", 1),
    ("Temperature", 1),
    ("ProcessedAt", 1),
])

# =========================================================
# MQTT
# =========================================================
mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="S2_Grupo34"
)


def ligar_mqtt():
    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            print("[S2] Ligado ao broker MQTT.")
        else:
            print(f"[S2] Erro na ligação MQTT: {reason_code}")

    mqtt_client.on_connect = on_connect
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()


# =========================================================
# AUXILIARES
# =========================================================
def agora_utc():
    return datetime.now(timezone.utc)


def normalizar_valor(valor):
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, datetime):
        return valor.isoformat()
    return valor


def normalizar_documento(documento):
    return {chave: normalizar_valor(valor) for chave, valor in documento.items()}


def marcar_processado(colecao, documento_id, extra=None):
    dados = {"ProcessedAt": agora_utc()}
    if extra:
        dados.update(extra)

    colecao.update_one(
        {"_id": documento_id},
        {"$set": dados}
    )


def guardar_flagged(tipo, documento, motivo, classificacao="invalid"):
    col_flagged.insert_one({
        "Tipo": tipo,
        "Classificacao": classificacao,
        "Motivo": motivo,
        "Documento": normalizar_documento(documento),
        "FlaggedAt": agora_utc()
    })


def enviar_para_mqtt(tipo, documento):
    payload = {
        "tipo": tipo,
        "documento": normalizar_documento(documento),
        "SentTimeStamp": agora_utc().isoformat()
    }

    # QoS 2 porque estes dados já seguem validados para escrita final em MySQL.
    info = mqtt_client.publish(
        MQTT_TOPIC_TO_SQL,
        json.dumps(payload, ensure_ascii=False),
        qos=2
    )
    info.wait_for_publish()

    print(f"[S2] Documento enviado para S3 ({tipo}) -> {documento['_id']}")


def data_valida(valor):
    if valor is None:
        return False
    if isinstance(valor, datetime):
        return True

    try:
        datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


# =========================================================
# VALIDAÇÃO
# =========================================================
def validar_movimento(documento):
    campos = ["Player", "Marsami", "RoomOrigin", "RoomDestiny", "Status"]
    for campo in campos:
        if campo not in documento:
            return False, f"Campo em falta: {campo}", "invalid"

    try:
        player = int(documento["Player"])
        marsami = int(documento["Marsami"])
        origem = int(documento["RoomOrigin"])
        destino = int(documento["RoomDestiny"])
        status = int(documento["Status"])
    except (ValueError, TypeError):
        return False, "Tipos de dados inválidos", "invalid"

    if any(v < 0 for v in [player, marsami, origem, destino]):
        return False, "Valor negativo detetado", "invalid"

    if status not in [0, 1, 2]:
        return False, f"Status inválido: {status}", "invalid"

    return True, None, "normal"


def validar_som(documento):
    # As mensagens de som do simulador usam Player, Hour e Sound.
    # Não é exigido campo Room.
    campos = ["Player", "Sound", "Hour"]
    for campo in campos:
        if campo not in documento:
            return False, f"Campo em falta: {campo}", "invalid"

    try:
        player = int(documento["Player"])
        sound = float(documento["Sound"])
    except (ValueError, TypeError):
        return False, "Tipos de dados inválidos", "invalid"

    if player < 0:
        return False, "Player negativo", "invalid"

    if not data_valida(documento.get("Hour")):
        return False, "Hora inválida", "invalid"

    if sound < 0 or sound > 140:
        return False, f"Som fora do intervalo plausível: {sound}", "outlier"

    return True, None, "normal"


def validar_temperatura(documento):
    # As mensagens de temperatura do simulador usam Player, Hour e Temperature.
    # Não é exigido campo Room.
    campos = ["Player", "Temperature", "Hour"]
    for campo in campos:
        if campo not in documento:
            return False, f"Campo em falta: {campo}", "invalid"

    try:
        player = int(documento["Player"])
        temperatura = float(documento["Temperature"])
    except (ValueError, TypeError):
        return False, "Tipos de dados inválidos", "invalid"

    if player < 0:
        return False, "Player negativo", "invalid"

    if not data_valida(documento.get("Hour")):
        return False, "Hora inválida", "invalid"

    if temperatura < -50 or temperatura > 100:
        return False, f"Temperatura fora do intervalo plausível: {temperatura}", "outlier"

    return True, None, "normal"


def documento_valido(tipo, documento):
    if tipo == "movement":
        return validar_movimento(documento)
    if tipo == "sound":
        return validar_som(documento)
    if tipo == "temperature":
        return validar_temperatura(documento)
    return False, "Tipo desconhecido", "invalid"



# =========================================================
# OUTLIERS POR VARIAÇÃO FACE À ÚLTIMA LEITURA VÁLIDA
# =========================================================
def obter_ultimo_valor_valido(colecao, player, campo_valor, documento_id_atual):
    """
    Procura a última leitura válida já enviada para o S3/MySQL.
    Não usa documentos flagged nem duplicados, porque só os documentos enviados
    recebem SentToSql=True.
    """
    ultimo = colecao.find_one(
        {
            "_id": {"$ne": documento_id_atual},
            "Player": player,
            campo_valor: {"$exists": True},
            "SentToSql": True,
            "ProcessedAt": {"$ne": None},
        },
        sort=[("ProcessedAt", -1), ("_id", -1)]
    )

    if not ultimo:
        return None

    try:
        return float(ultimo[campo_valor])
    except (ValueError, TypeError):
        return None


def fora_intervalo_mais_menos_150(valor_atual, ultimo_valor):
    """
    Verifica se valor_atual está fora do intervalo:
    ultimo_valor - 150% até ultimo_valor + 150%.

    Usa abs(ultimo_valor) para funcionar também se a temperatura anterior for negativa.
    Exemplo:
      ultimo = 20 -> margem = 30 -> intervalo [-10, 50]
      ultimo = -10 -> margem = 15 -> intervalo [-25, 5]
    """
    margem = abs(ultimo_valor) * PERCENTAGEM_VARIACAO_OUTLIER

    # Evita margem zero quando a última leitura é 0.
    # Assim, um salto de 0 para um valor muito alto continua a ser detetado.
    if margem == 0:
        margem = 1.0

    limite_inferior = ultimo_valor - margem
    limite_superior = ultimo_valor + margem

    return valor_atual < limite_inferior or valor_atual > limite_superior, limite_inferior, limite_superior


def verificar_outlier_variacao(tipo, documento):
    """
    Aplica a regra de outlier por variação apenas a som e temperatura.
    Se ainda não existir leitura válida anterior, não classifica como outlier.
    """
    if tipo == "sound":
        colecao = col_sound
        campo_valor = "Sound"
    elif tipo == "temperature":
        colecao = col_temperature
        campo_valor = "Temperature"
    else:
        return False, None

    try:
        player = int(documento["Player"])
        valor_atual = float(documento[campo_valor])
    except (ValueError, TypeError, KeyError):
        return False, None

    ultimo_valor = obter_ultimo_valor_valido(
        colecao,
        player,
        campo_valor,
        documento["_id"]
    )

    if ultimo_valor is None:
        return False, None

    fora, limite_inferior, limite_superior = fora_intervalo_mais_menos_150(
        valor_atual,
        ultimo_valor
    )

    if fora:
        motivo = (
            f"{campo_valor} fora do intervalo de variação permitido. "
            f"Último valor válido={ultimo_valor}; "
            f"intervalo aceite=[{limite_inferior:.2f}, {limite_superior:.2f}]; "
            f"valor atual={valor_atual}"
        )
        return True, motivo

    return False, None



# =========================================================
# DUPLICADOS RECENTES
# =========================================================
def filtro_documento_igual(tipo, documento):
    if tipo == "movement":
        return {
            "Player": documento.get("Player"),
            "Marsami": documento.get("Marsami"),
            "RoomOrigin": documento.get("RoomOrigin"),
            "RoomDestiny": documento.get("RoomDestiny"),
            "Status": documento.get("Status"),
        }

    if tipo == "sound":
        # Inclui Hour para não eliminar leituras legítimas iguais em segundos diferentes.
        return {
            "Player": documento.get("Player"),
            "Hour": documento.get("Hour"),
            "Sound": documento.get("Sound"),
        }

    if tipo == "temperature":
        # Inclui Hour para não eliminar leituras legítimas iguais em segundos diferentes.
        return {
            "Player": documento.get("Player"),
            "Hour": documento.get("Hour"),
            "Temperature": documento.get("Temperature"),
        }

    return {}


def existe_igual_tratado_recentemente(colecao, tipo, documento):
    limite = agora_utc() - timedelta(seconds=JANELA_DUPLICADOS_SEGUNDOS)

    filtro = filtro_documento_igual(tipo, documento)
    filtro["_id"] = {"$ne": documento["_id"]}
    filtro["ProcessedAt"] = {"$gte": limite}

    return colecao.find_one(filtro) is not None


# =========================================================
# PROCESSAMENTO
# =========================================================
def processar_colecao(colecao, tipo):
    documentos_por_tratar = colecao.find({
        "$or": [
            {"ProcessedAt": {"$exists": False}},
            {"ProcessedAt": None}
        ]
    }).sort("_id", 1)

    encontrados = 0
    enviados = 0
    ignorados = 0
    sinalizados = 0

    for documento in documentos_por_tratar:
        encontrados += 1

        valido, motivo, classificacao = documento_valido(tipo, documento)
        if not valido:
            guardar_flagged(tipo, documento, motivo, classificacao)
            marcar_processado(colecao, documento["_id"], {
                "ProcessStatus": "flagged",
                "Classification": classificacao
            })
            sinalizados += 1
            print(f"[S2] Documento sinalizado ({tipo}/{classificacao}) -> {documento['_id']}")
            continue

        if existe_igual_tratado_recentemente(colecao, tipo, documento):
            marcar_processado(colecao, documento["_id"], {
                "ProcessStatus": "duplicate"
            })
            ignorados += 1
            print(f"[S2] Duplicado recente ignorado ({tipo}) -> {documento['_id']}")
            continue

        # Outliers de som/temperatura por variação face à última leitura válida.
        eh_outlier, motivo_outlier = verificar_outlier_variacao(tipo, documento)
        if eh_outlier:
            guardar_flagged(tipo, documento, motivo_outlier, "outlier")
            marcar_processado(colecao, documento["_id"], {
                "ProcessStatus": "flagged",
                "Classification": "outlier"
            })
            sinalizados += 1
            print(f"[S2] Outlier por variação sinalizado ({tipo}) -> {documento['_id']}")
            continue

        # O S2 já não atualiza marsami_state/room_occupation/score_events no Mongo.
        # Essa lógica passou para Stored Procedures/Triggers no MySQL.
        enviar_para_mqtt(tipo, documento)
        marcar_processado(colecao, documento["_id"], {
            "ProcessStatus": "sent",
            "Classification": "normal",
            "SentToSql": True
        })
        enviados += 1

    if encontrados > 0:
        print(f"[S2] {tipo}: {enviados} enviados, {ignorados} ignorados, {sinalizados} sinalizados")


# =========================================================
# MAIN
# =========================================================
def main():
    ligar_mqtt()
    print("[S2] Serviço iniciado. Estado do labirinto será mantido no MySQL.")

    try:
        while True:
            processar_colecao(col_movement, "movement")
            processar_colecao(col_sound, "sound")
            processar_colecao(col_temperature, "temperature")

            print(f"[S2] Nova verificação dentro de {INTERVALO_SEGUNDOS} segundo(s).\n")
            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        print("[S2] Serviço terminado pelo utilizador.")

    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        mongo_client.close()


if __name__ == "__main__":
    main()
