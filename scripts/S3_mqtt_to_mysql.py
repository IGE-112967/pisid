import json
from datetime import datetime, timezone

import mysql.connector
from mysql.connector import Error
import paho.mqtt.client as mqtt

# =========================================================
# CONFIGURAÇÕES
# =========================================================
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC_TO_SQL = "pisid_to_sql_34"

DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = ""
DB_NAME = "pisid"


# =========================================================
# AUXILIARES
# =========================================================
def parse_datetime_for_mysql(value):
    """Converte datas ISO/strings do simulador para formato compatível com MySQL."""
    if value is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    text = str(value).replace("T", " ").replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(text)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        # Se a data vier num formato inesperado, não bloqueia a migração.
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def ligar_bd():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def chamar_sp(nome_sp, args):
    conn = None
    cursor = None

    try:
        conn = ligar_bd()
        cursor = conn.cursor()
        cursor.callproc(nome_sp, args)
        conn.commit()
        print(f"[S3] Stored procedure executada: {nome_sp}")

    except Error as e:
        if conn:
            conn.rollback()
        print(f"[S3] Erro MySQL ao executar {nome_sp}: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def processar_payload(payload_str):
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        print("[S3] Payload inválido: não é JSON")
        return

    tipo = payload.get("tipo")
    documento = payload.get("documento", {})
    sent_timestamp = payload.get("SentTimeStamp")

    if not tipo or not isinstance(documento, dict):
        print("[S3] Payload ignorado: formato inesperado")
        return

    if tipo == "movement":
        hora = parse_datetime_for_mysql(
            documento.get("Hour") or documento.get("ReceivedAt") or sent_timestamp
        )

        chamar_sp("sp_inserir_medicao_passagem", [
            int(documento["Player"]),
            hora,
            int(documento["RoomOrigin"]),
            int(documento["RoomDestiny"]),
            int(documento["Marsami"]),
            int(documento["Status"])
        ])
        return

    if tipo == "sound":
        hora = parse_datetime_for_mysql(documento.get("Hour") or sent_timestamp)

        chamar_sp("sp_inserir_som", [
            int(documento["Player"]),
            hora,
            float(documento["Sound"])
        ])
        return

    if tipo == "temperature":
        hora = parse_datetime_for_mysql(documento.get("Hour") or sent_timestamp)

        chamar_sp("sp_inserir_temperatura", [
            int(documento["Player"]),
            hora,
            float(documento["Temperature"])
        ])
        return

    print(f"[S3] Tipo desconhecido: {tipo}")


# =========================================================
# MQTT CALLBACKS
# =========================================================
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("[S3] Ligado ao broker MQTT")
        client.subscribe(MQTT_TOPIC_TO_SQL, qos=2)
        print(f"[S3] Subscrito a: {MQTT_TOPIC_TO_SQL}")
    else:
        print(f"[S3] Erro na ligação MQTT: {reason_code}")


def on_message(client, userdata, msg):
    payload_str = msg.payload.decode("utf-8", errors="replace")
    print(f"[S3] Mensagem recebida em {msg.topic}: {payload_str}")
    processar_payload(payload_str)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    print(f"[S3] Desligado do broker MQTT: {reason_code}")


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  S3 — MQTT intermédio → MySQL")
    print("=" * 50)

    mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="S3_Grupo34"
    )

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect

    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        print("\n[S3] A encerrar...")
    finally:
        mqtt_client.disconnect()
