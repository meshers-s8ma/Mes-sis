import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from app import create_app, socketio
from dotenv import load_dotenv
from config import config_by_name

# Загружаем переменные окружения из .env файла
load_dotenv()

# Определяем конфигурацию на основе переменной FLASK_ENV
config_name = os.environ.get('FLASK_ENV', 'development')
try:
    config_class = config_by_name[config_name]
except KeyError:
    sys.exit(f"Ошибка: Неверное имя конфигурации '{config_name}'. Доступные: {list(config_by_name.keys())}")

# Теперь create_app возвращает два объекта
app, socketio_instance = create_app(config_class)

# --- Настройка логирования ---
log_dir = os.path.join(app.instance_path, 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file_path = os.path.join(log_dir, 'app.log')

file_handler = RotatingFileHandler(
    log_file_path, maxBytes=10485760, backupCount=5, encoding='utf-8'
)

if config_name == 'development':
    log_format = '%(asctime)s - %(levelname)s - %(message)s [in %(pathname)s:%(lineno)d]'
else:
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
file_handler.setFormatter(logging.Formatter(log_format))

app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
# --- Конец настройки логирования ---


# Этот блок выполнится, только если запустить файл напрямую: `python run.py`
if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    
    app.logger.info(f"Server starting on http://{host}:{port} in '{config_name}' mode via Flask-SocketIO...")
    
    # Используем socketio.run() для запуска сервера,
    # это обеспечит поддержку WebSocket.
    # Для разработки allow_unsafe_werkzeug=True может быть полезен для авто-релоада.
    # В production-режиме (когда DEBUG=False) он не используется.
    socketio_instance.run(
        app, 
        host=host, 
        port=port, 
        allow_unsafe_werkzeug=app.config.get("DEBUG", False)
    )