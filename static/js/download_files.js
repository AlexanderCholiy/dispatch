document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('id_attachments');
    const fileList = document.querySelector('.file-list');
    const countLabel = document.querySelector('.file-uploader-count');
    const label = document.querySelector('.file-uploader-label');

    // === НАСТРОЙКИ ===
    const MAX_TOTAL_SIZE_MB = 20; 
    const MAX_TOTAL_SIZE_BYTES = MAX_TOTAL_SIZE_MB * 1024 * 1024;

    const showError = (message) => {
        alert(message);
    };

    const updateFileList = () => {
        fileList.innerHTML = '';
        const files = Array.from(fileInput.files);

        if (files.length === 0) {
            countLabel.style.display = 'none';
        } else {
            countLabel.style.display = 'inline';
            countLabel.textContent = `Всего ${files.length} файл(ов)`;
        }

        files.forEach((file, index) => {
            const li = document.createElement('li');
            
            const nameSpan = document.createElement('span');
            nameSpan.textContent = file.name;

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.textContent = '×';
            removeBtn.addEventListener('click', () => {
                const dt = new DataTransfer();
                files.forEach((f, i) => {
                    if (i !== index) dt.items.add(f);
                });
                fileInput.files = dt.files;
                updateFileList();
            });

            li.appendChild(nameSpan);
            li.appendChild(removeBtn);
            fileList.appendChild(li);
        });
    };

    // Функция проверки суммы
    const canAddFiles = (newFiles) => {
        const currentFiles = Array.from(fileInput.files);
        const currentSize = currentFiles.reduce((sum, f) => sum + f.size, 0);
        const newSize = newFiles.reduce((sum, f) => sum + f.size, 0);
        const totalSize = currentSize + newSize;

        if (totalSize > MAX_TOTAL_SIZE_BYTES) {
            showError(`Общий размер файлов превышает лимит в ${MAX_TOTAL_SIZE_MB} МБ.`);
            return false;
        }
        return true;
    };

    // --- Обработка выбора через кнопку ---
    fileInput.addEventListener('change', (e) => {
        const selectedFiles = Array.from(e.target.files);
        
        if (selectedFiles.length === 0) return;

        if (!canAddFiles(selectedFiles)) {
            e.target.value = ''; // Сброс выбора
            return;
        }
        updateFileList();
    });

    // --- Обработка Drag'n'Drop ---
    label.addEventListener('dragover', (e) => {
        e.preventDefault();
        label.classList.add('dragover');
    });

    label.addEventListener('dragleave', () => {
        label.classList.remove('dragover');
    });

    label.addEventListener('drop', (e) => {
        e.preventDefault();
        label.classList.remove('dragover');

        const droppedFiles = Array.from(e.dataTransfer.files);
        
        if (droppedFiles.length === 0) return;

        if (!canAddFiles(droppedFiles)) {
            return; // Игнорируем дроп
        }

        const dt = new DataTransfer();
        Array.from(fileInput.files).forEach(f => dt.items.add(f));
        droppedFiles.forEach(f => dt.items.add(f));

        fileInput.files = dt.files;
        updateFileList();
    });

    countLabel.style.display = 'none';
});