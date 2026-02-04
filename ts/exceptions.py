class EmptyTableError(Exception):
    """Исключение, когда в таблице нет данных для синхронизации."""
    def __init__(self, table_name: str, row_count: int):
        self.table_name = table_name
        self.message = (
            f'В таблице "{table_name}" отсутствуют данные для синхронизации. '
            f'Всего: {row_count} записей.'
        )
        super().__init__(self.message)


class TooManyRecordsToDeleteError(Exception):
    """Исключение попытки удаления слишком большого количество записей."""
    def __init__(
        self, table_name: str, attempted_count: int, max_allowed: int
    ):
        self.table_name = table_name
        self.attempted_count = attempted_count
        self.max_allowed = max_allowed
        self.message = (
            f'Попытка удалить {attempted_count} записей из таблицы '
            f'"{table_name}", что превышает допустимый лимит {max_allowed}. '
            'Операция отменена для предотвращения потери данных.'
        )
        super().__init__(self.message)
