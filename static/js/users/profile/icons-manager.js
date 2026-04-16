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
        // Если в форме уже что-то выбрано (при редактировании), подсвечиваем
        if (this.formSelect && this.formSelect.value) {
            this.selectIcon(this.formSelect.value);
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

        this.updateModeLabel('Иконка выбрана');
        this.toggleRemoveButton(true);
    }

    clearSelection() {
        document.querySelectorAll('.icon-item').forEach(el => el.classList.remove('selected'));
        
        if (this.formSelect) {
            this.formSelect.value = '';
        }

        // Возвращаем заглушку
        this.updatePreview('/static/css/img/default_avatars/fox.png'); // Или любой другой путь
        this.updateModeLabel('Нет иконки');
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