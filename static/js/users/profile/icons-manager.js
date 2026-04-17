// static/js/profile/icons-manager.js
import AVATAR_CONFIG from './constants.js';

class IconsManager {
    constructor() {
        this.gridElement = document.querySelector(AVATAR_CONFIG.selectors.iconsGrid);
        this.previewElement = document.querySelector(AVATAR_CONFIG.selectors.previewImg);
        this.formSelect = document.querySelector(AVATAR_CONFIG.selectors.formDefaultAvatar);
        this.removeBtn = document.querySelector(AVATAR_CONFIG.selectors.removeIconBtn);
        
        this.init();
    }

    init() {
        this.renderIcons();
        this.setupEvents();
        this.checkCurrentSelection();
    }

    renderIcons() {
        if (!this.gridElement) return;
        this.gridElement.innerHTML = '';

        AVATAR_CONFIG.availableIcons.forEach(filename => {
            const item = document.createElement('div');
            item.className = 'icon-item';
            item.dataset.value = filename;
            
            const img = document.createElement('img');
            img.src = `${AVATAR_CONFIG.iconsPath}${filename}`;
            img.alt = filename;
            
            item.appendChild(img);
            this.gridElement.appendChild(item);
        });
    }

    setupEvents() {
        this.gridElement.addEventListener('click', (e) => {
            const item = e.target.closest('.icon-item');
            if (!item) return;
            this.selectIcon(item.dataset.value);
        });

        if (this.removeBtn) {
            this.removeBtn.addEventListener('click', () => this.clearSelection());
        }
    }

    checkCurrentSelection() {
        // Проверяем, есть ли реально выбранная иконка в форме
        // Если value пустой или None, значит иконка не выбрана
        if (this.formSelect && this.formSelect.value) {
            console.log(`[IconsManager] Initial value detected: ${this.formSelect.value}`);
            this.selectIcon(this.formSelect.value);
        } else {
            // Если иконки нет, убедимся, что ничего не выбрано визуально
            document.querySelectorAll('.icon-item').forEach(el => el.classList.remove('selected'));
            // Убедимся, что превью показывает заглушку (если там еще не фото)
            // Это зависит от того, что отрисовал Django в шаблоне, но на всякий случай:
            const currentSrc = this.previewElement.src;
            if (currentSrc.includes('0__new_account.png')) {
                 this.updateModeLabel('Нет иконки');
            }
        }
    }

    selectIcon(filename) {
        // UI обновление
        document.querySelectorAll('.icon-item').forEach(el => el.classList.remove('selected'));
        const selectedItem = this.gridElement.querySelector(`[data-value="${filename}"]`);
        if (selectedItem) selectedItem.classList.add('selected');
        
        // Обновление превью
        this.updatePreview(`${AVATAR_CONFIG.iconsPath}${filename}`);
        
        // Синхронизация с формой Django
        if (this.formSelect) {
            this.formSelect.value = filename; 
        }
        
        // ВАЖНО: Если выбрали иконку, автоматически помечаем фото на удаление
        const dropZone = document.querySelector('#dropZone');
        if (dropZone && dropZone.classList.contains('has-file')) {
            const fileInput = document.querySelector('#id_avatar');
            
            // 1. СБРОСАЕМ ФАЙЛ ИЗ ИНПУТА (КРИТИЧНО!)
            // Если этого не сделать, Django увидит и файл, и галочку удаления -> Ошибка
            if (fileInput) {
                fileInput.value = ''; 
            }

            const clearCheckboxName = `${fileInput.name}-clear`;
            let clearCheckbox = document.querySelector(`input[name="${clearCheckboxName}"]`);
            
            if (!clearCheckbox) {
                clearCheckbox = document.createElement('input');
                clearCheckbox.type = 'checkbox';
                clearCheckbox.name = clearCheckboxName;
                clearCheckbox.id = clearCheckboxName + '_id';
                const wrapper = dropZone.querySelector('.django-hidden-input-wrapper');
                if (wrapper) wrapper.prepend(clearCheckbox);
            }
            clearCheckbox.checked = true;
            
            console.log('[IconsManager] Photo marked for deletion and input cleared.');
        }
        
        this.updateModeLabel('Иконка выбрана');
        this.toggleRemoveButton(true);
    }

    clearSelection() {
        document.querySelectorAll('.icon-item').forEach(el => el.classList.remove('selected'));
        
        if (this.formSelect) {
            this.formSelect.value = '';
        }
        
        // Важно: при очистке иконки, если фото нет, показываем заглушку
        // Но если фото ЕСТЬ, то мы не должны менять превью на заглушку!
        // Поэтому здесь мы НЕ меняем src, если там уже есть фото.
        // Однако, если мы очищаем иконку, а фото нет -> ставим заглушку.
        // Как узнать, есть ли фото? Проверим класс .has-file у dropZone
        const dropZone = document.querySelector('#dropZone');
        const hasPhoto = dropZone && dropZone.classList.contains('has-file');
        
        if (!hasPhoto) {
            this.updatePreview('/media/public/default_avatars/0__new_account.png');
            this.updateModeLabel('Нет иконки');
        } else {
            this.updateModeLabel('Фото загружено');
        }
        
        this.toggleRemoveButton(false);
    }

    updatePreview(src) {
        if (this.previewElement) {
            this.previewElement.src = src;
        }
    }

    updateModeLabel(text) {
        const label = document.querySelector(AVATAR_CONFIG.selectors.modeLabel);
        if (label) label.textContent = text;
    }

    toggleRemoveButton(show) {
        if (this.removeBtn) {
            this.removeBtn.classList.toggle('hidden', !show);
        }
    }
}

export default IconsManager;