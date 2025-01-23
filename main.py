from flask import Flask, request, jsonify, send_file
from asgiref.wsgi import WsgiToAsgi  # Адаптер для ASGI
import requests
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Получение API-ключа ElevenLabs
API_KEY = os.getenv("ELEVENLABS_API_KEY")
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# Инициализация Flask приложения
flask_app = Flask(__name__)

# Основной маршрут для генерации речи
@flask_app.route('/generate', methods=['POST'])
def generate_tts():
    try:
        data = request.json
        text = data.get("text")
        voice_id = data.get("voice_id", "21m00Tcm4TlvDq8ikWAM")  # ID голоса, по умолчанию стандартный

        if not text:
            return jsonify({"error": "Text is required"}), 400

        headers = {
            "xi-api-key": API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.85
            }
        }

        response = requests.post(f"{TTS_URL}/{voice_id}", json=payload, headers=headers)

        if response.status_code == 200:
            output_file = "output_audio.mp3"
            with open(output_file, "wb") as file:
                file.write(response.content)
            return send_file(output_file, mimetype="audio/mpeg")
        else:
            return jsonify({"error": response.json()}), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Главная страница для проверки
@flask_app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Welcome to the ElevenLabs TTS API!"})

# Обернуть Flask-приложение в ASGI-адаптер
app = WsgiToAsgi(flask_app)