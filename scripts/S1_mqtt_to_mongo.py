import json
from datetime import datetime

import paho.mqtt.client as mqtt
from pymongo import MongoClient

# =========================================================
# CONFIGURAÇÕES
# =========================================================
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883

GRUPO = 34
MQTT_TOPIC_MOV = f"pisid_mazemov_{GRUPO}"
MQTT_TOPIC_SOUND = f"pisid_mazesound_{GRUPO}"
MQTT_TOPIC_TEMP = f"pisid_mazetemp_{GRUPO}"

MONGO_URI = "mongodb://localhost:27017/?directConnection=true"
MONGO_DB = "pisid"

# =========================================================
# LIGAÇÃO AO MONGODB
# =========================================================
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

col_movement = db["movement"]
col_sound = db["sound"]
col_temperature = db["temperature"]

# =========================================================
# CALLBACKS MQTT
# =========================================================
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("[S1] Ligado ao broker MQTT")
        client.subscribe(MQTT_TOPIC_MOV, qos=1)
        client.subscribe(MQTT_TOPIC_SOUND, qos=1)
        client.subscribe(MQTT_TOPIC_TEMP, qos=1)
        print(f"[S1] Subscrito a: {MQTT_TOPIC_MOV}, {MQTT_TOPIC_SOUND}, {MQTT_TOPIC_TEMP}")
    else:
        print(f"[S1] Falha na ligação, código: {reason_code}")


def on_message(client, userdata, msg):
    topico = msg.topic
    payload = msg.payload.decode("utf-8", errors="replace")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        print(f"[S1] JSON inválido recebido em {topico}")
        return

    if not isinstance(data, dict):
        print(f"[S1] Mensagem ignorada em {topico}: formato inválido")
        return

    data["ReceivedAt"] = datetime.now()
    data["ProcessedAt"] = None

    if topico == MQTT_TOPIC_MOV:
        col_movement.insert_one(data)
        print("[S1] Movimento inserido")
        return

    if topico == MQTT_TOPIC_SOUND:
        col_sound.insert_one(data)
        print("[S1] Som inserido")
        return

    if topico == MQTT_TOPIC_TEMP:
        col_temperature.insert_one(data)
        print("[S1] Temperatura inserida")
        return

    print(f"[S1] Tópico desconhecido: {topico}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    print(f"[S1] Desligado (código={reason_code})")


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  S1 — MQTT → MongoDB")
    print("=" * 50)

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="S1_Grupo34"
    )

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[S1] A encerrar...")
    finally:
        client.disconnect()
        mongo_client.close()
