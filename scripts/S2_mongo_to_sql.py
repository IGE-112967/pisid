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

# Tópico intermédio para seguir para o S3 / MySQL.
MQTT_TOPIC_TO_SQL = "pisid_to_sql_34"

# Tópico dos atuadores do simulador.
MQTT_TOPIC_ACT = "pisid_mazeact"

MONGO_URI = "mongodb://localhost:27017/?directConnection=true"
MONGO_DB = "pisid"

# O relatório indica granularidade de 1 segundo.
INTERVALO_SEGUNDOS = 1
JANELA_DUPLICADOS_SEGUNDOS = 10
MAX_SCORE_POR_SALA = 3

# =========================================================
# LIGAÇÃO AO MONGO
# =========================================================
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

col_movement = db["movement"]
col_sound = db["sound"]
col_temperature = db["temperature"]
col_flagged = db["flagged"]

col_marsami_state = db["marsami_state"]
col_room_occupation = db["room_occupation"]
col_score_events = db["score_events"]

# Índices úteis para a migração incremental.
col_movement.create_index("ProcessedAt")
col_sound.create_index("ProcessedAt")
col_temperature.create_index("ProcessedAt")
col_movement.create_index([("Player", 1), ("Marsami", 1), ("RoomOrigin", 1), ("RoomDestiny", 1), ("Status", 1), ("ProcessedAt", 1)])
col_sound.create_index([("Player", 1), ("Hour", 1), ("Sound", 1), ("ProcessedAt", 1)])
col_temperature.create_index([("Player", 1), ("Hour", 1), ("Temperature", 1), ("ProcessedAt", 1)])

# =========================================================
# MQTT
# =========================================================
mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="S2_Grupo34"
)


def ligar_mqtt():
    def on_connect(client, userdata, flags, reason_code, properties):
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


def marcar_processado(colecao, documento_id):
    colecao.update_one(
        {"_id": documento_id},
        {"$set": {"ProcessedAt": agora_utc()}}
    )


def guardar_flagged(tipo, documento, motivo, classificacao="invalid"):
    col_flagged.insert_one({
        "Tipo": tipo,
        "Motivo": motivo,
        "Classificacao": classificacao,
        "Documento": normalizar_documento(documento),
        "FlaggedAt": agora_utc()
    })


def enviar_para_mqtt(tipo, documento):
    payload = {
        "tipo": tipo,
        "documento": normalizar_documento(documento),
        "SentTimeStamp": agora_utc().isoformat()
    }

    # QoS 2 porque esta mensagem já segue para escrita final em MySQL.
    info = mqtt_client.publish(
        MQTT_TOPIC_TO_SQL,
        json.dumps(payload, ensure_ascii=False),
        qos=2
    )
    info.wait_for_publish()

    print(f"[S2] Documento enviado para S3 ({tipo}) -> {documento['_id']}")


def enviar_score(player, room):
    payload = {
        "Type": "Score",
        "Player": int(player),
        "Room": int(room)
    }

    # QoS 1 é suficiente para atuação; se o broker/simulador duplicar, o limite de score é controlado.
    info = mqtt_client.publish(
        MQTT_TOPIC_ACT,
        json.dumps(payload, ensure_ascii=False),
        qos=1
    )
    info.wait_for_publish()

    print(f"[S2] Score enviado -> Player={player}, Room={room}")


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
    # O enunciado do simulador não inclui Room nas mensagens de som.
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
    # O enunciado do simulador não inclui Room nas mensagens de temperatura.
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
# TRATAMENTO DE MARSAMIS / OCUPAÇÃO / SCORE EM MONGO
# =========================================================
def obter_paridade(marsami):
    return "even" if int(marsami) % 2 == 0 else "odd"


def obter_estado_marsami(player, marsami):
    return col_marsami_state.find_one({
        "Player": int(player),
        "Marsami": int(marsami)
    })


def guardar_estado_marsami(player, marsami, room, parity, active=True):
    col_marsami_state.update_one(
        {"Player": int(player), "Marsami": int(marsami)},
        {"$set": {
            "CurrentRoom": int(room),
            "Parity": parity,
            "Active": bool(active),
            "LastUpdate": agora_utc()
        }},
        upsert=True
    )


def garantir_documento_sala(player, room):
    col_room_occupation.update_one(
        {"Player": int(player), "Room": int(room)},
        {"$setOnInsert": {
            "OddCount": 0,
            "EvenCount": 0,
            "TotalCount": 0,
            "TriggerCount": 0,
            "LastUpdate": agora_utc()
        }},
        upsert=True
    )


def atualizar_ocupacao(player, room, parity, delta):
    player = int(player)
    room = int(room)

    if room <= 0:
        return

    garantir_documento_sala(player, room)
    sala = col_room_occupation.find_one({"Player": player, "Room": room})

    odd = int(sala.get("OddCount", 0))
    even = int(sala.get("EvenCount", 0))

    if parity == "odd":
        odd = max(0, odd + delta)
    else:
        even = max(0, even + delta)

    col_room_occupation.update_one(
        {"Player": player, "Room": room},
        {"$set": {
            "OddCount": odd,
            "EvenCount": even,
            "TotalCount": odd + even,
            "LastUpdate": agora_utc()
        }}
    )


def verificar_e_disparar_score(player, room):
    player = int(player)
    room = int(room)

    if room <= 0:
        return

    sala = col_room_occupation.find_one({"Player": player, "Room": room})
    if not sala:
        return

    odd = int(sala.get("OddCount", 0))
    even = int(sala.get("EvenCount", 0))
    trigger_count = int(sala.get("TriggerCount", 0))

    if odd > 0 and odd == even and trigger_count < MAX_SCORE_POR_SALA:
        ultimo_evento = col_score_events.find_one({
            "Player": player,
            "Room": room,
            "OddCount": odd,
            "EvenCount": even
        })

        if ultimo_evento:
            return

        enviar_score(player, room)

        col_score_events.insert_one({
            "Player": player,
            "Room": room,
            "OddCount": odd,
            "EvenCount": even,
            "TriggeredAt": agora_utc()
        })

        col_room_occupation.update_one(
            {"Player": player, "Room": room},
            {"$inc": {"TriggerCount": 1}, "$set": {"LastUpdate": agora_utc()}}
        )


def tratar_movimento(documento):
    player = int(documento["Player"])
    marsami = int(documento["Marsami"])
    origem = int(documento["RoomOrigin"])
    destino = int(documento["RoomDestiny"])

    parity = obter_paridade(marsami)
    estado_atual = obter_estado_marsami(player, marsami)

    if origem == 0 and destino > 0:
        if estado_atual and int(estado_atual.get("CurrentRoom", 0)) > 0:
            atualizar_ocupacao(player, int(estado_atual["CurrentRoom"]), parity, -1)

        guardar_estado_marsami(player, marsami, destino, parity, True)
        atualizar_ocupacao(player, destino, parity, 1)
        verificar_e_disparar_score(player, destino)
        return

    if origem == 0 and destino == 0:
        if estado_atual:
            sala_atual = int(estado_atual.get("CurrentRoom", 0))
            guardar_estado_marsami(player, marsami, sala_atual, parity, False)
            verificar_e_disparar_score(player, sala_atual)
        return

    if origem > 0 and destino > 0:
        if estado_atual and int(estado_atual.get("CurrentRoom", 0)) > 0:
            sala_anterior = int(estado_atual["CurrentRoom"])
        else:
            sala_anterior = origem

        atualizar_ocupacao(player, sala_anterior, parity, -1)
        atualizar_ocupacao(player, destino, parity, 1)
        guardar_estado_marsami(player, marsami, destino, parity, True)
        verificar_e_disparar_score(player, sala_anterior)
        verificar_e_disparar_score(player, destino)
        return

    guardar_flagged("movement", documento, "Combinação origem/destino não esperada", "invalid")


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
            marcar_processado(colecao, documento["_id"])
            sinalizados += 1
            print(f"[S2] Documento sinalizado ({tipo}/{classificacao}) -> {documento['_id']}")
            continue

        if existe_igual_tratado_recentemente(colecao, tipo, documento):
            marcar_processado(colecao, documento["_id"])
            ignorados += 1
            print(f"[S2] Duplicado recente ignorado ({tipo}) -> {documento['_id']}")
            continue

        if tipo == "movement":
            tratar_movimento(documento)

        enviar_para_mqtt(tipo, documento)
        marcar_processado(colecao, documento["_id"])
        enviados += 1

    if encontrados > 0:
        print(f"[S2] {tipo}: {enviados} enviados, {ignorados} ignorados, {sinalizados} sinalizados")


# =========================================================
# MAIN
# =========================================================
def main():
    ligar_mqtt()
    print("[S2] Serviço iniciado.")

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
