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
MQTT_TOPIC_TO_SQL = "pisid_to_sql_34"

MONGO_URI = "mongodb://localhost:27017/?directConnection=true"
MONGO_DB = "pisid"

INTERVALO_SEGUNDOS = 5
JANELA_DUPLICADOS_SEGUNDOS = 10

# =========================================================
# LIGAÇÃO AO MONGO
# =========================================================
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

col_movement = db["movement"]
col_sound = db["sound"]
col_temperature = db["temperature"]
col_flagged = db["flagged"]

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


def guardar_flagged(tipo, documento, motivo):
    col_flagged.insert_one({
        "Tipo": tipo,
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

    info = mqtt_client.publish(
        MQTT_TOPIC_TO_SQL,
        json.dumps(payload, ensure_ascii=False),
        qos=1
    )
    info.wait_for_publish()

    print(f"[S2] Documento enviado ({tipo}) -> {documento['_id']}")


# =========================================================
# VALIDAÇÃO SIMPLES
# =========================================================
def validar_movimento(documento):
    campos = ["Player", "Marsami", "RoomOrigin", "RoomDestiny", "Status"]
    for campo in campos:
        if campo not in documento:
            return False, f"Campo em falta: {campo}"

    try:
        player = int(documento["Player"])
        marsami = int(documento["Marsami"])
        origem = int(documento["RoomOrigin"])
        destino = int(documento["RoomDestiny"])
        status = int(documento["Status"])
    except (ValueError, TypeError):
        return False, "Tipos de dados inválidos"

    if any(v < 0 for v in [player, marsami, origem, destino]):
        return False, "Valor negativo detetado"

    if status not in [0, 1, 2]:
        return False, f"Status inválido: {status}"

    return True, None


def validar_som(documento):
    campos = ["Room", "Sound", "Hour"]
    for campo in campos:
        if campo not in documento:
            return False, f"Campo em falta: {campo}"

    try:
        room = int(documento["Room"])
        sound = float(documento["Sound"])
    except (ValueError, TypeError):
        return False, "Tipos de dados inválidos"

    if room < 0:
        return False, "Room negativo"

    if sound < 0 or sound > 140:
        return False, f"Som fora do intervalo plausível: {sound}"

    return True, None


def validar_temperatura(documento):
    campos = ["Room", "Temperature", "Hour"]
    for campo in campos:
        if campo not in documento:
            return False, f"Campo em falta: {campo}"

    try:
        room = int(documento["Room"])
        temperatura = float(documento["Temperature"])
    except (ValueError, TypeError):
        return False, "Tipos de dados inválidos"

    if room < 0:
        return False, "Room negativo"

    if temperatura < -50 or temperatura > 100:
        return False, f"Temperatura fora do intervalo plausível: {temperatura}"

    return True, None


def documento_valido(tipo, documento):
    if tipo == "movement":
        return validar_movimento(documento)

    if tipo == "sound":
        return validar_som(documento)

    if tipo == "temperature":
        return validar_temperatura(documento)

    return False, "Tipo desconhecido"


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
        return {
            "Room": documento.get("Room"),
            "Sound": documento.get("Sound"),
        }

    if tipo == "temperature":
        return {
            "Room": documento.get("Room"),
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

        valido, motivo = documento_valido(tipo, documento)
        if not valido:
            guardar_flagged(tipo, documento, motivo)
            marcar_processado(colecao, documento["_id"])
            sinalizados += 1
            print(f"[S2] Documento inválido sinalizado ({tipo}) -> {documento['_id']}")
            continue

        if existe_igual_tratado_recentemente(colecao, tipo, documento):
            marcar_processado(colecao, documento["_id"])
            ignorados += 1
            print(f"[S2] Duplicado recente ignorado ({tipo}) -> {documento['_id']}")
            continue

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

            print(f"[S2] Nova verificação dentro de {INTERVALO_SEGUNDOS} segundos.\n")
            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        print("[S2] Serviço terminado pelo utilizador.")

    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        mongo_client.close()


if __name__ == "__main__":
    main()
