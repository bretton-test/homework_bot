import logging
import time

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
from constants import TIMEOUT, RETRY_PERIOD, ENDPOINT, HEADERS
from exceptions import EnvironmentValueError, HttpStatusError, BotHandler

error_messages = {}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = BotHandler(messages=error_messages)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Check tokens for validity."""
    if not bool(PRACTICUM_TOKEN):
        logger.critical(
            'Отсутствует обязательная переменная окружения: PRACTICUM_TOKEN'
        )
        raise EnvironmentValueError('PRACTICUM_TOKEN')
    if not bool(TELEGRAM_TOKEN):
        logger.critical(
            'Отсутствует обязательная переменная окружения: TELEGRAM_TOKEN'
        )
        raise EnvironmentValueError('TELEGRAM_TOKEN')
    if not bool(TELEGRAM_CHAT_ID):
        logger.critical(
            'Отсутствует обязательная переменная окружения: TELEGRAM_CHAT_ID'
        )
        raise EnvironmentValueError('TELEGRAM_CHAT_ID')


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
        # homework_statuses.raise_for_status() - но это не проходит тесты
        if homework_statuses.status_code != 200:
            raise HttpStatusError(ENDPOINT, homework_statuses.status_code)

        return homework_statuses.json()
    except requests.exceptions.RequestException as error:
        logger.error(error)
    except ValueError as error:
        logger.error(error)


def check_response(response):
    """Проверка ответа API домашки."""
    if not isinstance(response, dict):
        raise TypeError('API возвращает неверный тип данных')
    answer = response.get(HOMEWORK_KEY)
    if not isinstance(answer, list):
        raise TypeError('API возвращает неверный тип данных')
    for item in answer:
        for key in HOMEWORK_KEYS:
            value = item.get(key)
            if not bool(value):
                raise ValueError(f'пустое значение параметра {key}')


def parse_status(homework):
    """Возвращает ответ из словаря домашки."""
    status = homework.get(STATUS_KEY)
    if not bool(status):
        raise ValueError('Api не возвращает статус')
    verdict = HOMEWORK_VERDICTS.get(status)
    if not bool(verdict):
        raise ValueError('Api возвращает недокументированный статус')
    homework_name = homework.get(HOMEWORK_NAME_KEY)
    if not bool(homework_name):
        raise ValueError(
            f'в ответе API домашки нет ключа "{HOMEWORK_NAME_KEY}" '
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_error_message(bot):
    """Обработка словаря ошибок.
    Отправляет сообщение в телеграмм.
    """
    global error_messages
    for key, item in error_messages.copy().items():
        if bool(item.get("new")) and send_message(bot, item.get("message")):
            error_messages[key] = {
                'message': item.get("message"),
                'new': False,
            }


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD
    check_tokens()
    while True:
        try:
            response = get_api_answer(timestamp)
            if bool(response):
                check_response(response)

                homeworks = response.get(HOMEWORK_KEY)
                timestamp = response.get(TIME_KEY)
                if bool(homeworks):
                    homework_status = parse_status(homeworks[0])
                    if bool(homework_status):
                        send_message(bot, homework_status)
                else:
                    logger.debug('нет новых статусов')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            send_error_message(bot)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
