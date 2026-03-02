document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('id_attachments');
    const fileList = document.querySelector('.file-list');
    const countLabel = document.querySelector('.file-uploader-count');
    const label = document.querySelector('.file-uploader-label');

    const updateFileList = () => {
        fileList.innerHTML = '';
        const files = Array.from(fileInput.files);

        if (files.length === 0) {
            countLabel.style.display = 'none'; // скрываем надпись
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

    // Стандартный выбор файлов
    fileInput.addEventListener('change', updateFileList);

    // Drag'n'Drop
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

        const dt = new DataTransfer();
        Array.from(fileInput.files).forEach(f => dt.items.add(f));
        Array.from(e.dataTransfer.files).forEach(f => dt.items.add(f));

        fileInput.files = dt.files;
        updateFileList();
    });

    // Изначально скрываем надпись
    countLabel.style.display = 'none';
});