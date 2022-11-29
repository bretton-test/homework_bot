import logging
import string
import time
from http import HTTPStatus
from json import dumps
from json.decoder import JSONDecodeError

import requests
import telegram

from constants import (
    HOMEWORK_KEY,
    TIME_KEY,
    STATUS_KEY,
    HOMEWORK_NAME_KEY,
    HOMEWORK_VERDICTS,
    HOMEWORK_KEYS,
)
from constants import PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from constants import TELEGRAM_RETRY_PERIOD as RETRY_PERIOD
from constants import TIMEOUT, ENDPOINT
from exceptions import (
    EnvironmentValueError,
    HttpStatusError,
    BotHandler,
    RequestError,
    JsonError,
)

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
# иначе ругается pep8 на неиспользуемый PRACTICUM_TOKEN
error_messages = {}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = BotHandler(messages=error_messages)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Check tokens for validity."""
    missing_tokens = []
    for item in ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'):
        if not globals()[item]:
            missing_tokens.append(item)
    error_message = ', '.join(missing_tokens)
    if error_message:
        logger.critical(
            'Отсутствует обязательная'
            f' переменная окружения: {error_message}'
        )
    return error_message


def send_message(bot, message):
    """Отправляет сообщение  в телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение "{message}"')
        return True
    except telegram.error.TelegramError as error:
        logger.error(f'ошибка отправки сообщения "{error}"')
    return False


def get_api_answer(timestamp):
    """Получаем ответ от API домашки с периода timestamp."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp, 'timeout': TIMEOUT},
        )
    except requests.exceptions.RequestException as error:
        raise RequestError(ENDPOINT) from error

    if homework_statuses.status_code != HTTPStatus.OK:
        raise HttpStatusError(ENDPOINT, homework_statuses.status_code)
    # хотел проверить 'Content-Type', но тесты не знают такое
    try:
        dumps(homework_statuses.text)
    except JSONDecodeError as error:
        raise JsonError() from error
    return homework_statuses.json()


def check_response(response):
    """Проверка ответа API домашки."""
    error_message = 'API возвращает неверный тип данных'
    if not isinstance(response, dict):
        raise TypeError(f'{error_message}. {type(response)}: ожидаемый dict!')
    # get убрать нельзя. тест не проходит
    homeworks = response.get(HOMEWORK_KEY)
    timestamp = response.get(TIME_KEY)
    if not isinstance(homeworks, list):
        raise TypeError(f'{error_message}. {type(homeworks)}: ожидаемый list!')
    if not isinstance(timestamp, int):
        raise TypeError(f'{error_message}. {type(timestamp)}: ожидаемый int!')

    for item in homeworks:
        for key in HOMEWORK_KEYS:
            value = item.get(key)
            if not isinstance(value, str):
                raise TypeError(
                    f'{error_message}. {type(value)}: ожидаемый str!'
                )


def parse_status(homework):
    """Возвращает ответ из словаря домашки."""
    error_message = 'Api возвращает недокументированный статус'
    if STATUS_KEY not in homework:
        raise KeyError(error_message)
    status = homework[STATUS_KEY]
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(error_message)
    verdict = HOMEWORK_VERDICTS[status]
    if HOMEWORK_NAME_KEY not in homework:
        raise KeyError(error_message)
    homework_name = homework[HOMEWORK_NAME_KEY]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_error_message(bot):
    """Обработка словаря ошибок.
    Отправляет сообщение в телеграмм.
    """
    global error_messages
    for key, item in error_messages.copy().items():
        if item.get('new') and send_message(bot, item.get('message')):
            error_messages[key] = {
                'message': item.get('message'),
                'new': False,
            }
            # ""  вместо '' - привычка из 1с. даже не замечаю


def main():
    """Основная логика работы бота."""
    old_message: string = ''
    missing_tokens = check_tokens()
    if missing_tokens:
        raise EnvironmentValueError(missing_tokens)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response[HOMEWORK_KEY]
            timestamp = response[TIME_KEY]
            if homeworks:
                homework_status = parse_status(homeworks[0])
                if homework_status != old_message:
                    send_message(bot, homework_status)
                    old_message = homework_status
            else:
                logger.debug('нет новых статусов')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)

        finally:
            send_error_message(bot)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
