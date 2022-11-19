import logging
import os
import json
import requests
import sys
import time

import telegram
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.DEBUG,
    filename='telegram_bot.log',
    format='%(asctime)s, %(levelname)s, %(message)s',
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
STATUS_OK = 200


class MyException(Exception):
    """Моя супер разработка."""

    pass


def send_message(bot, message):
    """
    Отправляет сообщение в ТГ.
    На вход экземпляр класса bot и само сообщение
    """
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info(f'Сообщение {message} отправлено')
    except MyException as error:
        logging.error(f'Ошибка отправки сообщения {error}')
        send_message(bot, 'Сообщение не удалось отправить')


def get_api_answer(current_timestamp):
    """
    делает запрос к API-сервиса.
    на вход - временная метка. в случае успеха json->py
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_status = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework_status.status_code != STATUS_OK:
            message = f'Сбой. Ответ сервера {homework_status.status_code}'
            logging.error(message)
            send_message(bot, message)
    except requests.exceptions.RequestException as error:
        logging.error(f'Сервер Яндекс.Практикум вернул ошибку: {error}')
        send_message(f'Сервер Яндекс.Практикум вернул ошибку: {error}')
    try:
        return homework_status.json()
    except json.JSONDecodeError:
        logging.error('Сервер вернул невалидный json')
        send_message('Сервер вернул невалидный json')


def check_response(response):
    """
    проверяет ответ API на корректность.
    на вход - ответ API.
    в случае успеха возвращает ответ API с ключом 'homeworks'
    """
    if not isinstance(response['homeworks'], list):
        logging.error('Запрос к серверу пришёл не в виде списка')
        send_message(bot, 'Запрос к серверу пришёл не в виде списка')
        raise MyException('Запрос к серверу пришёл не в виде списка')
    logging.info(f'Получен список работ {response}')
    return response['homeworks']


def parse_status(homework):
    """
    извлекает из информации о конкретной домашней работе статус этой работы.
    на вход - один элемент из списка домашних заданий.
    в случае успеха возвращает строку для отправки в ТГ
    """
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        logging.error('Статус не обнаружен в списке')
        send_message(bot, 'Статус не обнаружен в списке')
        raise MyException('Статус не обнаружен в списке')
    verdict = HOMEWORK_STATUSES[homework_status]
    mess = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    return mess


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """
    Основная логика работы программы.
    Сделать запрос к API. Проверить ответ.
    Если есть обновления — получить статус и отправить сообщение
    Подождать некоторое время и сделать новый запрос.
    """
    if not check_tokens():
        logging.critical('Не найден обязательный токен')
        exit('Не найден обязательный токен')
    global bot
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logging.debug('Бот запущен')
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if len(homework) == 0:
                send_message(bot, 'Bероятно, вы еще не отправили работу')
            else:
                send_message(bot, parse_status(homework[0]))
            current_timestamp = response.get('current_date', current_timestamp)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
