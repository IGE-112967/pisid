import json
import threading
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt
from pymongo import MongoClient

# =========================================================
# CONFIGURAÇÕES
# =========================================================
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883

GRUPO = 34
MQTT_TOPIC_MOV = f"pisid_mazemov_34"
MQTT_TOPIC_SOUND = f"pisid_mazesound_34"
MQTT_TOPIC_TEMP = f"pisid_mazetemp_34"

MONGO_URI = "mongodb://localhost:27017/?directConnection=true"
MONGO_DB = "pisid"

JANELA_SPAM_MOV = 3
JANELA_SPAM_SOUND = 2
JANELA_SPAM_TEMP = 2

# =========================================================
# LIGAÇÃO AO MONGODB
# =========================================================
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

col_movement = db["movement"]
col_sound = db["sound"]
col_temperature = db["temperature"]
col_flagged = db["flagged"]

lock = threading.Lock()

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================
def parse_datetime(valor):
    if isinstance(valor, datetime):
        return valor

    if not isinstance(valor, str):
        raise ValueError("Valor de data inválido")

    formatos = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formatos:
        try:
            return datetime.strptime(valor, fmt)
        except ValueError:
            pass

    raise ValueError(f"Formato de data inválido: {valor}")


def registar_flagged(dados, motivo, topico=None, payload=None):
    doc = {
        "Motivo": motivo,
        "ReceivedAt": datetime.now()
    }

    if topico is not None:
        doc["Topico"] = topico

    if payload is not None:
        doc["Payload"] = payload

    if isinstance(dados, dict):
        doc.update(dados)

    col_flagged.insert_one(doc)


# =========================================================
# VALIDAÇÕES
# =========================================================
def validar_movimento(data):
    campos = ["Player", "Marsami", "RoomOrigin", "RoomDestiny", "Status"]
    for campo in campos:
        if campo not in data:
            return False, f"Campo em falta: {campo}"

    try:
        player = int(data["Player"])
        marsami = int(data["Marsami"])
        origem = int(data["RoomOrigin"])
        destino = int(data["RoomDestiny"])
        status = int(data["Status"])
    except (ValueError, TypeError):
        return False, "Tipos de dados inválidos"

    if any(v < 0 for v in [player, marsami, origem, destino]):
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
        player = int(data["Player"])
        sound = float(data["Sound"])
        parse_datetime(data["Hour"])
    except (ValueError, TypeError) as e:
        return False, str(e)

    if player < 0:
        return False, "Player negativo"

    if sound < 0 or sound > 140:
        return False, f"Som fora do intervalo: {sound}"

    return True, None


def validar_temperatura(data):
    campos = ["Player", "Hour", "Temperature"]
    for campo in campos:
        if campo not in data:
            return False, f"Campo em falta: {campo}"

    try:
        player = int(data["Player"])
        temperatura = float(data["Temperature"])
        parse_datetime(data["Hour"])
    except (ValueError, TypeError) as e:
        return False, str(e)

    if player < 0:
        return False, "Player negativo"

    if temperatura < -50 or temperatura > 100:
        return False, f"Temperatura fora do intervalo plausível: {temperatura}"

    return True, None


# =========================================================
# SPAM IMEDIATO
# =========================================================
def e_spam_movimento(data):
    limite = datetime.now() - timedelta(seconds=JANELA_SPAM_MOV)

    return col_movement.find_one({
        "Player": int(data["Player"]),
        "Marsami": int(data["Marsami"]),
        "RoomOrigin": int(data["RoomOrigin"]),
        "RoomDestiny": int(data["RoomDestiny"]),
        "Status": int(data["Status"]),
        "ReceivedAt": {"$gte": limite}
    }) is not None


def e_spam_som(data):
    limite = datetime.now() - timedelta(seconds=JANELA_SPAM_SOUND)

    return col_sound.find_one({
        "Player": int(data["Player"]),
        "Sound": float(data["Sound"]),
        "ReceivedAt": {"$gte": limite}
    }) is not None


def e_spam_temperatura(data):
    limite = datetime.now() - timedelta(seconds=JANELA_SPAM_TEMP)

    return col_temperature.find_one({
        "Player": int(data["Player"]),
        "Temperature": float(data["Temperature"]),
        "ReceivedAt": {"$gte": limite}
    }) is not None


# =========================================================
# CLASSIFICAÇÃO DA MENSAGEM
# =========================================================
def tipo_da_mensagem(topico, data):
    if topico == MQTT_TOPIC_MOV or all(
        campo in data for campo in ["Player", "Marsami", "RoomOrigin", "RoomDestiny", "Status"]
    ):
        return "movement"

    if topico == MQTT_TOPIC_SOUND or all(
        campo in data for campo in ["Player", "Hour", "Sound"]
    ):
        return "sound"

    if topico == MQTT_TOPIC_TEMP or all(
        campo in data for campo in ["Player", "Hour", "Temperature"]
    ):
        return "temperature"

    return None


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
        with lock:
            registar_flagged({}, "Bad Message - JSON inválido", topico=topico, payload=payload)
        print(f"[S1] JSON inválido no tópico {topico}")
        return

    if not isinstance(data, dict):
        with lock:
            registar_flagged({}, "Bad Message - JSON não é objeto", topico=topico, payload=payload)
        print(f"[S1] Mensagem ignorada: formato inválido em {topico}")
        return

    data["ReceivedAt"] = datetime.now()
    data["ProcessedAt"] = None

    tipo = tipo_da_mensagem(topico, data)

    with lock:
        if tipo == "movement":
            valido, motivo = validar_movimento(data)
            if not valido:
                registar_flagged(data, f"Bad Message - {motivo}", topico=topico)
                print(f"[S1] Movimento inválido ({motivo})")
                return

            if e_spam_movimento(data):
                registar_flagged(data, "Spam", topico=topico)
                print("[S1] Spam de movimento detetado")
                return

            col_movement.insert_one(data)
            print(
                f"[S1] Movimento inserido: "
                f"Player={data['Player']} Marsami={data['Marsami']} "
                f"{data['RoomOrigin']}->{data['RoomDestiny']}"
            )
            return

        if tipo == "sound":
            valido, motivo = validar_som(data)
            if not valido:
                registar_flagged(data, f"Bad Message - {motivo}", topico=topico)
                print(f"[S1] Som inválido ({motivo})")
                return

            if e_spam_som(data):
                registar_flagged(data, "Spam", topico=topico)
                print("[S1] Spam de som detetado")
                return

            col_sound.insert_one(data)
            print(f"[S1] Som inserido: Player={data['Player']} Sound={data['Sound']}")
            return

        if tipo == "temperature":
            valido, motivo = validar_temperatura(data)
            if not valido:
                registar_flagged(data, f"Bad Message - {motivo}", topico=topico)
                print(f"[S1] Temperatura inválida ({motivo})")
                return

            if e_spam_temperatura(data):
                registar_flagged(data, "Spam", topico=topico)
                print("[S1] Spam de temperatura detetado")
                return

            col_temperature.insert_one(data)
            print(f"[S1] Temperatura inserida: Player={data['Player']} Temp={data['Temperature']}")
            return

        registar_flagged(data, "Tópico ou estrutura desconhecida", topico=topico, payload=payload)
        print(f"[S1] Mensagem desconhecida em {topico}")


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
