// static/js/profile/main.js
import AVATAR_CONFIG from './constants.js';
import IconsManager from './icons-manager.js';
import PhotoManager from './photo-manager.js';

document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('#avatarSelector');
    if (!container) return;

    const photoManager = new PhotoManager();
    const iconsManager = new IconsManager();
    
    const tabs = document.querySelectorAll('.tab-btn');
    const sections = document.querySelectorAll('.avatar-section');
    const form = document.getElementById('profileForm');
    const submitBtn = document.querySelector('.submit-button');

    // Логика переключения табов (ТОЛЬКО визуальная)
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;
            
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            sections.forEach(s => s.classList.add('hidden'));
            
            if (targetTab === 'photo') {
                document.querySelector('#section-photo').classList.remove('hidden');
                // НЕТ СБРОСА ЗНАЧЕНИЯ ЗДЕСЬ! Мы просто скрываем секцию.
                // Значение в formSelect остается, чтобы пользователь мог вернуть его, если передумает.
            } else {
                document.querySelector('#section-icons').classList.remove('hidden');
                // НЕТ СБРОСА ФОТО ЗДЕСЬ!
            }
        });
    });

    // Обработчик отправки формы
    if (form) {
        form.addEventListener('submit', (e) => {
            const activeTab = document.querySelector('.tab-btn.active').dataset.tab;
            
            if (activeTab === 'photo') {
                // Если отправляем с вкладки "Фото", принудительно сбрасываем иконку
                if (iconsManager && iconsManager.formSelect) {
                    console.log('[Main] Saving with Photo tab active. Clearing default_avatar.');
                    iconsManager.formSelect.value = '';
                    iconsManager.clearSelection(); // Уберем подсветку визуально перед отправкой
                }
            } else if (activeTab === 'icon') {
                // Если отправляем с вкладки "Иконки", убедимся, что фото помечено на удаление
                // (Логика уже есть в selectIcon, но на всякий случай проверим наличие галочки)
                const dropZone = document.querySelector('#dropZone');
                if (dropZone && dropZone.classList.contains('has-file')) {
                    const fileInput = document.querySelector('#id_avatar');
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
                    // Очищаем инпут файла, чтобы не было конфликта
                    if (fileInput) fileInput.value = '';
                }
            }
        });
    }

    const previewContainer = document.querySelector('#previewContainer');
    if (previewContainer) {
        previewContainer.addEventListener('click', () => {
            const activeTab = document.querySelector('.tab-btn.active').dataset.tab;
            if (activeTab === 'photo') {
                document.querySelector('#id_avatar').click();
            }
        });
    }
});