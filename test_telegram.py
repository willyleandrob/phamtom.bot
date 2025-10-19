import requests
import tomllib

# Leer config.toml
with open("config.toml", "rb") as f:
    cfg = tomllib.load(f)

bot_token = cfg["telegram"]["bot_token"]
chat_id = cfg["telegram"]["chat_id"]

mensaje = "✅ ¡Conexión con Telegram exitosa! Tu bot está funcionando correctamente 🚀"

# Enviar mensaje
r = requests.post(
    f"https://api.telegram.org/bot{bot_token}/sendMessage",
    json={"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"},
)

if r.status_code == 200:
    print("✅ Mensaje enviado correctamente a Telegram.")
else:
    print("❌ Error al enviar mensaje. Código:", r.status_code)
    print(r.text)
