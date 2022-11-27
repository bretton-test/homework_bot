import sys
from logging import StreamHandler

ERROR_LEVEL = 40


class EnvironmentValueError(Exception):
    """Исключение вызывается при отсутствии переменной окружения.
    Attributes:
        env_variable -- отсутствующая переменная.
        message -- сообщение об ошибке.
    """

    def __init__(
        self,
        env_variable,
        message="Отсутствует обязательная переменная окружения:",
    ):
        self.env_variable = env_variable
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        message = f'{self.message} {self.env_variable}'
        return message


class HttpStatusError(Exception):
    """Исключение вызывается при статусе ответа != 200.
    Attributes:
        endpoint_name -- адрес.
        status_code -- код ответа API.
        message -- сообщение об ошибке.
    """

    def __init__(
        self,
        endpoint_name,
        status_code,
        message='',
    ):
        self.endpoint_name = endpoint_name
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        message = (
            f'{self.message} Эндпоинт {self.endpoint_name} недоступен.'
            f' Код ответа API: {self.status_code}'
        )
        return message


class BotHandler(StreamHandler):
    """Обработчик для логгера. Добавляет ошибки уровня ERROR
    и выше в словарь ошибок.
    """

    stream = sys.stdout

    def __init__(self, messages=None):
        StreamHandler.__init__(self, self.stream)
        self.messages = messages

    def emit(self, record):
        super().emit(record)
        if record.levelno >= ERROR_LEVEL:
            key = f'{record.lineno}: {record.module}'
            if not self.messages.get(key):
                self.messages[key] = {
                    'message': self.format(record),
                    'new': True,
                }
