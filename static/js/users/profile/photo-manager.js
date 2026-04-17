// static/js/profile/photo-manager.js
import AVATAR_CONFIG from './constants.js';

class PhotoManager {
    constructor() {
        this.dropZone = document.querySelector(AVATAR_CONFIG.selectors.dropZone);
        this.fileInput = document.querySelector(AVATAR_CONFIG.selectors.fileInput);
        this.previewElement = document.querySelector(AVATAR_CONFIG.selectors.previewImg);
        this.removeBtn = document.querySelector(AVATAR_CONFIG.selectors.removePhotoBtn);
        
        // 1. ПРОВЕРКА НАЧАЛЬНОГО СОСТОЯНИЯ
        // Проверяем, есть ли src у картинки превью (кроме заглушки)
        // Или проверяем, есть ли ссылка на файл в зоне загрузки (если она была сгенерирована Django)
        
        const hasExistingAvatar = AVATAR_CONFIG.hasUserPhoto;
        
        if (hasExistingAvatar) {
            this.setHasFileState(true);
            this.updateModeLabel('Фото загружено');
        } else {
            this.setHasFileState(false);
        }

        this.init();
    }

    init() {
        this.setupDragDrop();
        this.setupFileInput();
        this.setupRemoveButton();
    }

    setupDragDrop() {
        if (!this.dropZone) return;
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            this.dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            this.dropZone.addEventListener(eventName, () => this.dropZone.classList.add('drag-over'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            this.dropZone.addEventListener(eventName, () => this.dropZone.classList.remove('drag-over'), false);
        });

        this.dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt.files.length) this.handleFiles(dt.files);
        });
    }

    setupFileInput() {
        if (!this.fileInput) return;
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) this.handleFiles(e.target.files);
        });
    }

    handleFiles(files) {
        const file = files[0];
        if (!this.validateFile(file)) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            this.previewElement.src = e.target.result;
            this.updateModeLabel('Новое фото загружено');
            this.setHasFileState(true);
        };
        reader.readAsDataURL(file);
    }

    setHasFileState(hasFile) {
        if (!this.dropZone || !this.removeBtn) return;

        if (hasFile) {
            this.dropZone.classList.add('has-file');
            this.removeBtn.classList.remove('hidden');
        } else {
            this.dropZone.classList.remove('has-file');
            this.removeBtn.classList.add('hidden');
        }
    }

    setupRemoveButton() {
        if (!this.removeBtn) return;
        
        this.removeBtn.addEventListener('click', (e) => {
            e.preventDefault(); 
            
            // 1. Сначала очищаем инпут файла
            if (this.fileInput) {
                this.fileInput.value = '';
            }
            
            // 2. Потом ставим галочку очистки
            const clearCheckboxName = `${this.fileInput.name}-clear`;
            let clearCheckbox = document.querySelector(`input[name="${clearCheckboxName}"]`);
            
            if (!clearCheckbox) {
                // ... создание чекбокса ...
                clearCheckbox = document.createElement('input');
                clearCheckbox.type = 'checkbox';
                clearCheckbox.name = clearCheckboxName;
                clearCheckbox.id = clearCheckboxName + '_id';
                const wrapper = this.dropZone.querySelector('.django-hidden-input-wrapper');
                if (wrapper) wrapper.prepend(clearCheckbox);
            }
            
            clearCheckbox.checked = true;
            
            // 3. Визуальный сброс
            this.previewElement.src = '/media/public/default_avatars/0__new_account.png';
            this.updateModeLabel('Фото удалено');
            this.setHasFileState(false);
        });
    }

    validateFile(file) {
        const ext = file.name.split('.').pop().toLowerCase();
        if (!AVATAR_CONFIG.allowedExtensions.includes(ext)) {
            alert('Разрешены только JPG и PNG.');
            return false;
        }
        if (file.size > AVATAR_CONFIG.maxFileSize) {
            alert('Файл слишком большой (макс 5MB).');
            return false;
        }
        return true;
    }

    updateModeLabel(text) {
        const label = document.querySelector(AVATAR_CONFIG.selectors.modeLabel);
        if (label) label.textContent = text;
    }

    resetPhotoState() {
        if (this.fileInput) this.fileInput.value = '';
        this.previewElement.src = '/media/public/default_avatars/0__new_account.png';
        this.updateModeLabel('Фото удалено');
        this.setHasFileState(false);
        
        // Создаем чекбокс очистки, чтобы форма знала о желании удалить
        const clearCheckboxName = `${this.fileInput.name}-clear`;
        let clearCheckbox = document.querySelector(`input[name="${clearCheckboxName}"]`);
        if (!clearCheckbox) {
            clearCheckbox = document.createElement('input');
            clearCheckbox.type = 'checkbox';
            clearCheckbox.name = clearCheckboxName;
            clearCheckbox.id = clearCheckboxName + '_id';
            const wrapper = this.dropZone.querySelector('.django-hidden-input-wrapper');
            if (wrapper) wrapper.prepend(clearCheckbox);
        }
        clearCheckbox.checked = true;
    }
}

export default PhotoManager;