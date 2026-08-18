import os
import re

from users.constants import DEFAULT_AVATARS_DIR


def natural_sort_key(filename):
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split(r'(\d+)', filename)
    ]


def get_default_avatars():
    choices = []

    if os.path.exists(DEFAULT_AVATARS_DIR):

        files = os.listdir(DEFAULT_AVATARS_DIR)

        image_files = [
            f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]

        hash_pattern = re.compile(
            r'\.([a-f0-9]{8,16})\.(png|jpg|jpeg)$', re.IGNORECASE
        )

        seen_basenames = set()

        for filename in sorted(image_files, key=natural_sort_key):
            if hash_pattern.search(filename):
                continue

            name_without_ext = os.path.splitext(filename)[0]

            if name_without_ext.startswith('0__new_account'):
                continue

            if name_without_ext not in seen_basenames:
                seen_basenames.add(name_without_ext)
                choices.append((filename, f'{name_without_ext} ({filename})'))

    return choices
