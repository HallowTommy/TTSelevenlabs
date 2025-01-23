from flask import Flask, request, jsonify
from asgiref.wsgi import WsgiToAsgi  # Адаптер для ASGI
import requests
import os
import uuid
import paramiko  # Для передачи файлов через SCP
from pydub import AudioSegment
from dotenv import load_dotenv
import logging
import subprocess

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s]: %(message)s')
logger = logging.getLogger()

# Загрузка переменных окружения из файла .env
load_dotenv()

# Проверка наличия ffmpeg
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("ffmpeg is installed and ready.")
    except FileNotFoundError:
        logger.error("ffmpeg is not installed. Please install ffmpeg to proceed.")
        raise RuntimeError("ffmpeg is required but not installed.")
    except subprocess.CalledProcessError as e:
        logger.error("An error occurred while checking ffmpeg: %s", e)
        raise RuntimeError("ffmpeg is installed but may not be working correctly.")

check_ffmpeg()  # Проверяем наличие ffmpeg перед обработкой аудио

# Получение API-ключа ElevenLabs
API_KEY = os.getenv("ELEVENLABS_API_KEY")
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# Настройки для VPS
VPS_HOST = "95.179.190.232"  # IP-адрес вашего VPS
VPS_USERNAME = "root"       # Имя пользователя
VPS_PASSWORD = "2c}Gd)QMri,@#f$Y"     # Пароль
VPS_DEST_PATH = "/tmp/tts_files"  # Путь для хранения файлов на VPS

STATIC_DIR = "static"
os.makedirs(STATIC_DIR, exist_ok=True)
logger.info("Static directory created: %s", STATIC_DIR)

# Инициализация Flask приложения
flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "TTS API is running!"})

def get_audio_length(file_path):
    """
    Определяет длину аудиофайла (в секундах).
    """
    try:
        audio = AudioSegment.from_file(file_path)
        duration = len(audio) / 1000  # Переводим миллисекунды в секунды
        return round(duration, 2)  # Округляем до 2 знаков
    except Exception as e:
        logger.error("Error getting audio length: %s", str(e))
        return 0

@flask_app.route("/generate", methods=["POST"])
def generate_audio():
    try:
        logger.info("Received request to generate audio.")

        # Получение текста из запроса
        data = request.get_json()
        text = data.get("text", "")
        voice_id = data.get("voice_id", "pO3rCaEbT3xVc0h3pPoG")  # Стандартный голос
        logger.debug("Text received: %s", text)

        if not text:
            logger.error("No text provided in the request.")
            return jsonify({"error": "Text is required"}), 400

        # Генерация имени файла
        output_filename = f"{uuid.uuid4().hex}.mp3"
        output_path = os.path.join(STATIC_DIR, output_filename)
        logger.debug("Generated output file path: %s", output_path)

        # Генерация аудио через ElevenLabs API
        headers = {
            "xi-api-key": API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "voice_settings": {
                "stability": 0,
                "similarity_boost": 0
            }
        }
        response = requests.post(f"{TTS_URL}/{voice_id}", json=payload, headers=headers)

        if response.status_code == 200:
            with open(output_path, "wb") as file:
                file.write(response.content)
            logger.info("Audio file generated: %s", output_path)
        else:
            logger.error("Error generating audio: %s", response.text)
            return jsonify({"error": response.text}), response.status_code

        # Определяем длину аудиофайла
        audio_length = get_audio_length(output_path)
        logger.info("Audio length calculated: %s seconds", audio_length)

        # Отправка файла на VPS
        logger.info("Attempting to send file to VPS: %s", VPS_HOST)
        send_file_to_vps(output_path)

        # Удаление временного файла
        os.remove(output_path)
        logger.info("Temporary file deleted: %s", output_path)

        # Возвращаем длину аудиофайла в JSON-ответе
        return jsonify({
            "status": "success",
            "message": "File sent to VPS successfully.",
            "audio_length": audio_length
        })

    except Exception as e:
        logger.error("Error during audio generation: %s", str(e))
        return jsonify({"error": str(e)}), 500

def send_file_to_vps(file_path):
    """
    Отправляет файл на VPS через SCP.
    """
    try:
        logger.info("Connecting to VPS at %s", VPS_HOST)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VPS_HOST, username=VPS_USERNAME, password=VPS_PASSWORD)
        logger.info("Connected to VPS successfully.")

        # Передача файла
        sftp = ssh.open_sftp()
        dest_path = os.path.join(VPS_DEST_PATH, os.path.basename(file_path))
        sftp.put(file_path, dest_path)
        sftp.close()
        ssh.close()
        logger.info("File successfully sent to VPS: %s", file_path)

    except Exception as e:
        logger.error("Error sending file to VPS: %s", str(e))
        raise

# Обернуть Flask-приложение в ASGI-адаптер
app = WsgiToAsgi(flask_app)
