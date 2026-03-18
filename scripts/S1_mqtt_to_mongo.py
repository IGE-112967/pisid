import paho.mqtt.client as mqtt
from pymongo import MongoClient
from datetime import datetime, timedelta
import json
import threading

# ─────────────────────────────────────────
#  CONFIGURAÇÕES
# ─────────────────────────────────────────
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC_MOV = "pisid_mazemov_6"
MQTT_TOPIC_SOUND = "pisid_mazesound_6"

MONGO_URI = "mongodb://localhost:27017/?directConnection=true"
MONGO_DB = "pisid"

# ─────────────────────────────────────────
#  LIGAÇÃO AO MONGODB
# ─────────────────────────────────────────
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

col_movement = db["movement"]
col_sound = db["sound"]
col_flagged = db["flagged"]

lock = threading.Lock()

# ─────────────────────────────────────────
#  VALIDAÇÃO DE FORMATO
# ─────────────────────────────────────────
def validar_movimento(data):
    campos = ["Player", "Marsami", "RoomOrigin", "RoomDestiny", "Status"]
    for campo in campos:
        if campo not in data:
            return False, f"Campo em falta: {campo}"

    try:
        player = int(data["Player"])
        marsami = int(data["Marsami"])
        origin = int(data["RoomOrigin"])
        destiny = int(data["RoomDestiny"])
        status = int(data["Status"])
    except (ValueError, TypeError):
        return False, "Tipo de dados inválido"

    if any(v < 0 for v in [player, marsami, origin, destiny]):
        return False, "Valor negativo detetado"

    if status not in [0, 1, 2]:
        return False, f"Status inválido: {status}"

    return True, None


def validar_som(data):
    campos = ["Player", "Hour", "Sound"]
    for campo in campos:
        if campo not in data:
            return False, f"Campo em falta: {campo}"

    try:
        sound = float(data["Sound"])
        player = int(data["Player"])
    except (ValueError, TypeError):
        return False, "Tipo de dados inválido"

    if sound < 0 or sound > 140:
        return False, f"Som fora do intervalo (0-140): {sound}"

    if player < 0:
        return False, "Player negativo"

    try:
        datetime.strptime(data["Hour"], "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return False, f"Formato de data inválido: {data['Hour']}"

    return True, None


# ─────────────────────────────────────────
#  DETEÇÃO DE SPAM
# ─────────────────────────────────────────
def e_spam_movimento(data):
    limite = datetime.now() - timedelta(seconds=3)

    resultado = col_movement.find_one({
        "Player": int(data["Player"]),
        "Marsami": int(data["Marsami"]),
        "RoomOrigin": int(data["RoomOrigin"]),
        "RoomDestiny": int(data["RoomDestiny"]),
        "Status": int(data["Status"]),
        "ReceivedAt": {"$gte": limite}
    })
    return resultado is not None


def e_spam_som(data):
    limite = datetime.now() - timedelta(seconds=2)

    resultado = col_sound.find_one({
        "Player": int(data["Player"]),
        "Sound": float(data["Sound"]),
        "ReceivedAt": {"$gte": limite}
    })
    return resultado is not None


# ─────────────────────────────────────────
#  CALLBACKS MQTT
# ─────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[S1] Ligado ao broker MQTT")
        client.subscribe(MQTT_TOPIC_MOV, qos=1)
        client.subscribe(MQTT_TOPIC_SOUND, qos=1)
        print(f"[S1] Subscrito a: {MQTT_TOPIC_MOV} e {MQTT_TOPIC_SOUND}")
    else:
        print(f"[S1] Falha na ligação, código: {rc}")


def on_message(client, userdata, msg):
    topico = msg.topic
    payload = msg.payload.decode("utf-8")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        with lock:
            col_flagged.insert_one({
                "Payload": payload,
                "Topico": topico,
                "Motivo": "Bad Message - JSON inválido",
                "ReceivedAt": datetime.now()
            })
        print(f"[S1] Bad Message: {payload}")
        return

    data["ReceivedAt"] = datetime.now()

    with lock:
        if topico == MQTT_TOPIC_MOV:
            valido, motivo = validar_movimento(data)
            if not valido:
                col_flagged.insert_one({**data, "Motivo": f"Bad Message - {motivo}"})
                print(f"[S1] Movimento inválido ({motivo})")
                return

            if e_spam_movimento(data):
                col_flagged.insert_one({**data, "Motivo": "Spam"})
                print("[S1] Spam de movimento detetado")
                return

            col_movement.insert_one(data)
            print(f"[S1] Movimento inserido: Player={data['Player']} Marsami={data['Marsami']}")

        elif topico == MQTT_TOPIC_SOUND:
            valido, motivo = validar_som(data)
            if not valido:
                col_flagged.insert_one({**data, "Motivo": f"Bad Message - {motivo}"})
                print(f"[S1] Som inválido ({motivo})")
                return

            if e_spam_som(data):
                col_flagged.insert_one({**data, "Motivo": "Spam"})
                print("[S1] Spam de som detetado")
                return

            try:
                hora = datetime.strptime(data["Hour"], "%Y-%m-%d %H:%M:%S.%f")
                diff = (datetime.now() - hora).total_seconds()
                if diff > 120:
                    col_flagged.insert_one({**data, "Motivo": "TimeStamp Antigo"})
                    print(f"[S1] Timestamp antigo ({diff:.0f}s) — inserido na mesma")
            except Exception:
                pass

            col_sound.insert_one(data)
            print(f"[S1] Som inserido: Player={data['Player']} Sound={data['Sound']}")

        else:
            col_flagged.insert_one({
                "Payload": payload,
                "Topico": topico,
                "Motivo": "Tópico desconhecido",
                "ReceivedAt": datetime.now()
            })
            print(f"[S1] Tópico desconhecido: {topico}")


def on_disconnect(client, userdata, rc):
    print(f"[S1] Desligado (rc={rc}). A reconectar...")


# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  S1 — MQTT → MongoDB")
    print("=" * 50)

    client = mqtt.Client(client_id="S1_Grupo6", clean_session=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[S1] A encerrar...")
        client.disconnect()
        mongo_client.close()
