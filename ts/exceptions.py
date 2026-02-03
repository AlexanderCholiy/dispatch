class EmptyTableError(Exception):
    """Исключение, когда в таблице нет данных для синхронизации."""
    def __init__(self, table_name: str, row_count: int):
        self.table_name = table_name
        self.message = (
            f'В таблице "{table_name}" отсутствуют данные для синхронизации. '
            f'Всего: {row_count} записей.'
        )
        super().__init__(self.message)
