import json
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt
from pymongo import MongoClient
from bson import ObjectId

# =========================================================
# CONFIGURAÇÕES
# =========================================================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "pisid_to_sql_6"

MONGO_URI = "mongodb://localhost:27017/?directConnection=true"
MONGO_DB = "pisid"

# Verificação periódica
INTERVALO_SEGUNDOS = 5

# Janela temporal para evitar duplicados recentes
JANELA_DUPLICADOS_SEGUNDOS = 10


# =========================================================
# LIGAÇÃO AO MONGO
# =========================================================
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

col_movement = db["movement"]
col_sound = db["sound"]
col_temperature = db["temperature"]


# =========================================================
# LIGAÇÃO AO MQTT
# =========================================================
mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="S2_Grupo6"
)


def ligar_mqtt():
    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("[S2] Ligado ao broker MQTT.")
        else:
            print(f"[S2] Erro na ligação ao MQTT. Código: {reason_code}")

    mqtt_client.on_connect = on_connect
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()


# =========================================================
# FUNÇÕES AUXILIARES
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
    doc = {}
    for chave, valor in documento.items():
        doc[chave] = normalizar_valor(valor)
    return doc


def filtro_documento_igual(tipo, documento):
    """
    Define quais os campos relevantes para considerar
    que dois documentos são iguais.
    """
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
    """
    Verifica se já existe outro documento igual que tenha sido
    tratado dentro da janela temporal definida.
    """
    limite = agora_utc() - timedelta(seconds=JANELA_DUPLICADOS_SEGUNDOS)

    filtro = filtro_documento_igual(tipo, documento)
    filtro["_id"] = {"$ne": documento["_id"]}
    filtro["ProcessedAt"] = {"$gte": limite}

    return colecao.find_one(filtro) is not None


def marcar_processado(colecao, documento_id):
    colecao.update_one(
        {"_id": documento_id},
        {"$set": {"ProcessedAt": agora_utc()}}
    )


def enviar_para_mqtt(tipo, documento):
    payload = {
        "tipo": tipo,
        "documento": normalizar_documento(documento),
        "SentTimeStamp": agora_utc().isoformat()
    }

    mqtt_client.publish(
        MQTT_TOPIC,
        json.dumps(payload, ensure_ascii=False),
        qos=1
    )

    print(f"[S2] Documento enviado ({tipo}) -> {documento['_id']}")


def processar_colecao(colecao, tipo):
    """
    Processa apenas documentos ainda não tratados.
    """
    documentos_por_tratar = colecao.find({
        "$or": [
            {"ProcessedAt": {"$exists": False}},
            {"ProcessedAt": None}
        ]
    })

    for documento in documentos_por_tratar:
        if existe_igual_tratado_recentemente(colecao, tipo, documento):
            print(f"[S2] Duplicado recente ignorado ({tipo}) -> {documento['_id']}")
            marcar_processado(colecao, documento["_id"])
            continue

        enviar_para_mqtt(tipo, documento)
        marcar_processado(colecao, documento["_id"])


# =========================================================
# CICLO PRINCIPAL
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
