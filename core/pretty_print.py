import re
import shutil
from datetime import datetime
from typing import Optional

from colorama import Back, Fore, Style

from .constants import DEBUG_MODE as DEBUG


class PrettyPrint:

    @staticmethod
    def _formatted_print(
        *segments: tuple[str | object, bool],
        text_color: str = Fore.LIGHTBLUE_EX,
        var_color: str = Fore.WHITE,
        text_style: str = Style.NORMAL,
        var_style: str = Style.NORMAL,
    ):
        """
        Вывод стилизованного текста с цветами и стилями для текста и
        переменных.

        Аргументы:
            *segments: кортежи (value, is_variable), где:
                value (str | object): текст или переменная для вывода
                is_variable (bool): True — переменная, False — обычный текст
            text_color (str): цвет обычного текста
            var_color (str): цвет переменных
            text_style (str): стиль обычного текста (Style.NORMAL / BRIGHT /
            DIM)
            var_style (str): стиль переменных
        """
        if not DEBUG:
            return

        result = ""
        for value, is_variable in segments:
            color = var_color if is_variable else text_color
            style = var_style if is_variable else text_style
            result += f'{style}{color}{value} '
        result += Style.RESET_ALL
        print(result)

    @staticmethod
    def debug_print(*segments):
        PrettyPrint._formatted_print(
            *segments,
            text_color=Fore.LIGHTWHITE_EX,
            var_color=Fore.WHITE,
            text_style=Style.DIM,
            var_style=Style.NORMAL,
        )

    @staticmethod
    def info_print(*segments):
        PrettyPrint._formatted_print(
            *segments,
            text_color=Fore.LIGHTBLUE_EX,
            var_color=Fore.LIGHTWHITE_EX,
            text_style=Style.NORMAL,
            var_style=Style.NORMAL,
        )

    @staticmethod
    def success_print(*segments):
        PrettyPrint._formatted_print(
            *segments,
            text_color=Fore.GREEN,
            var_color=Fore.LIGHTWHITE_EX,
            text_style=Style.NORMAL,
            var_style=Style.NORMAL,
        )

    @staticmethod
    def warning_print(*segments):
        PrettyPrint._formatted_print(
            *segments,
            text_color=Fore.LIGHTYELLOW_EX,
            var_color=Fore.WHITE,
            text_style=Style.NORMAL,
            var_style=Style.BRIGHT,
        )

    @staticmethod
    def error_print(*segments):
        PrettyPrint._formatted_print(
            *segments,
            text_color=Fore.LIGHTRED_EX,
            var_color=Fore.WHITE,
            text_style=Style.NORMAL,
            var_style=Style.BRIGHT,
        )

    @staticmethod
    def critical_print(*segments):
        PrettyPrint._formatted_print(
            *segments,
            text_color=Fore.RED,
            var_color=Fore.LIGHTWHITE_EX,
            text_style=Style.BRIGHT,
            var_style=Style.BRIGHT,
        )

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Удаляет ANSI-коды из строки для корректного измерения длины."""
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        return ansi_escape.sub('', text)

    @staticmethod
    def _get_bg_color(
        progress: float, percent_bg: str, bar_length: int
    ) -> str:
        """Динамический фон для прогрес бара."""
        filled_length = int(bar_length * progress)
        if filled_length < 2 * bar_length // 3:
            return Back.LIGHTBLACK_EX
        return percent_bg

    @staticmethod
    def _progress_bar(
        iteration: int,
        total: int,
        message: str,
        bar_color: str,
        percent_bg: str,
        bar_length: Optional[int],
    ) -> None:
        if total == 0 or not DEBUG:
            return

        total -= 1
        iteration = min(iteration, total)
        progress = iteration / total
        percent = progress * 100
        percent_text = f' {percent:5.1f}% '
        bar_length = bar_length or 50

        filled_len = int(bar_length * progress)
        bar = ''
        i = 0

        while i < bar_length:
            if i == bar_length // 2 - len(percent_text) // 2:
                bar += PrettyPrint._get_bg_color(
                    progress, percent_bg, bar_length
                ) + Fore.WHITE + Style.BRIGHT + percent_text + Style.RESET_ALL
                i += len(percent_text)
                continue
            if i < filled_len:
                bar += bar_color + '█' + Style.RESET_ALL
            else:
                bar += Fore.LIGHTBLACK_EX + '█' + Style.RESET_ALL
            i += 1

        bar_display = f'{Fore.BLACK}|{bar}{Fore.BLACK}|{Style.RESET_ALL}'

        terminal_width = shutil.get_terminal_size((80, 20)).columns
        message_part = f'{bar_color}{message}{Style.RESET_ALL}'
        right_part = (
            f'{Fore.WHITE}{Style.BRIGHT}{iteration}/{total}{Style.RESET_ALL}'
        )
        left_text = f'{message_part} {right_part}'

        spacing = (
            terminal_width
            - len(PrettyPrint._strip_ansi(left_text))
            - len(PrettyPrint._strip_ansi(bar_display))
        )
        spacing = max(spacing, 0)

        print(f'{left_text}{" " * spacing}{bar_display}', end='\r')

        if iteration == total:
            print(Style.RESET_ALL)

    @staticmethod
    def progress_bar_debug(
        i: int, total: int, msg='Загрузка:', bar_length: Optional[int] = None
    ):
        PrettyPrint._progress_bar(
            i, total, msg, Fore.LIGHTWHITE_EX, Back.LIGHTWHITE_EX, bar_length)

    @staticmethod
    def progress_bar_info(
        i: int, total: int, msg='Загрузка:', bar_length: Optional[int] = None
    ):
        PrettyPrint._progress_bar(
            i, total, msg, Fore.LIGHTBLUE_EX, Back.LIGHTBLUE_EX, bar_length
        )

    @staticmethod
    def progress_bar_success(
        i: int, total: int, msg='Загрузка:', bar_length: Optional[int] = None
    ):
        PrettyPrint._progress_bar(
            i, total, msg, Fore.GREEN, Back.GREEN, bar_length
        )

    @staticmethod
    def progress_bar_warning(
        i: int, total: int, msg='Загрузка:', bar_length: Optional[int] = None
    ):
        PrettyPrint._progress_bar(
            i, total, msg, Fore.LIGHTYELLOW_EX, Back.LIGHTYELLOW_EX, bar_length
        )

    @staticmethod
    def progress_bar_error(
        i: int, total: int, msg='Загрузка:', bar_length: Optional[int] = None
    ):
        PrettyPrint._progress_bar(
            i, total, msg, Fore.LIGHTRED_EX, Back.LIGHTRED_EX, bar_length
        )

    @staticmethod
    def progress_bar_critical(
        i: int, total: int, msg='Загрузка:', bar_length: Optional[int] = None
    ):
        PrettyPrint._progress_bar(
            i, total, msg, Fore.RED, Back.RED, bar_length
        )


def test_print():
    test_msg = (
        ('Текущее время:', False),
        (datetime.now().hour, True), ('ч', False),
        (datetime.now().minute, True), ('мин.', False),
    )
    N = 1_000

    PrettyPrint.debug_print(*test_msg)
    [PrettyPrint.progress_bar_debug(i, N) for i in range(N)]

    PrettyPrint.info_print(*test_msg)
    [PrettyPrint.progress_bar_info(i, N) for i in range(N)]

    PrettyPrint.success_print(*test_msg)
    [PrettyPrint.progress_bar_success(i, N) for i in range(N)]

    PrettyPrint.warning_print(*test_msg)
    [PrettyPrint.progress_bar_warning(i, N) for i in range(N)]

    PrettyPrint.error_print(*test_msg)
    [PrettyPrint.progress_bar_error(i, N) for i in range(N)]

    PrettyPrint.critical_print(*test_msg)
    [PrettyPrint.progress_bar_critical(i, N) for i in range(N)]
