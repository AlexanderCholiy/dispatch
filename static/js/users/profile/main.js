// static/js/profile/main.js
import AVATAR_CONFIG from './constants.js';
import IconsManager from './icons-manager.js';
import PhotoManager from './photo-manager.js';

document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector(AVATAR_CONFIG.selectors.container);
    if (!container) return;

    const photoManager = new PhotoManager();
    const iconsManager = new IconsManager();

    const tabs = document.querySelectorAll(AVATAR_CONFIG.selectors.tabs);
    const sections = document.querySelectorAll(AVATAR_CONFIG.selectors.sections);

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;
            
            // Переключение классов
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            sections.forEach(s => s.classList.add('hidden'));
            
            if (targetTab === 'photo') {
                document.querySelector(AVATAR_CONFIG.selectors.photoSection).classList.remove('hidden');
                // Логика: если выбрано фото, сбрасываем иконку в форме (визуально)
                // Но не очищаем поле формы, пока пользователь не выберет фото или не нажмет "удалить"
            } else {
                document.querySelector(AVATAR_CONFIG.selectors.iconSection).classList.remove('hidden');
            }
        });
    });

    // Клик по превью открывает диалог загрузки фото
    const previewContainer = document.querySelector(AVATAR_CONFIG.selectors.previewContainer);
    if (previewContainer) {
        previewContainer.addEventListener('click', () => {
            const activeTab = document.querySelector('.tab-btn.active').dataset.tab;
            if (activeTab === 'photo') {
                document.querySelector(AVATAR_CONFIG.selectors.fileInput).click();
            }
        });
    }
});