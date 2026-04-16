import os
from users.constants import DEFAULT_AVATARS_DIR


def get_default_avatars():
    """Считывает файлы из папки статических иконок."""
    choices = []
    if os.path.exists(DEFAULT_AVATARS_DIR):
        for filename in sorted(os.listdir(DEFAULT_AVATARS_DIR)):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                name_without_ext = os.path.splitext(filename)[0]

                if name_without_ext == '0__new_account':
                    continue

                choices.append((filename, f'{name_without_ext} ({filename})'))

    return choices
