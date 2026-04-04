// static/js/comments/ui.js

export class CommentsUI {
    constructor(containerId, configElement) {
        this.container = document.getElementById(containerId);
        this.listEl = document.getElementById('cw-list');
        this.emptyEl = document.getElementById('cw-empty');
        this.inputEl = document.getElementById('cw-input');
        this.submitBtn = document.getElementById('cw-submit');
        this.cancelBtn = document.getElementById('cw-cancel-edit');
        this.editIdInput = document.getElementById('cw-edit-id');
        this.errorMsg = document.getElementById('cw-error-msg');
        this.charCount = document.createElement('span'); 
        
        this.sortAscBtn = document.getElementById('comment-sort-asc');
        this.sortDescBtn = document.getElementById('comment-sort-desc');
        this.filterSelect = document.getElementById('filter-my-comments');
        
        this.rawComments = []; 
        this.currentSort = 'desc'; 
        this.currentFilter = 'all'; 
        this.deletePendingId = null; 
        this.MAX_LENGTH = 2048;
        
        this.loadSettings();
        this.createCustomModal();
        this.initCharCounter();
        this.initListeners();
    }

    loadSettings() {
        const incidentId = this.container.dataset.incidentId || 'global';
        const savedSort = localStorage.getItem(`cw-sort-${incidentId}`);
        const savedFilter = localStorage.getItem(`cw-filter-${incidentId}`);
        
        if (savedSort) {
            this.currentSort = savedSort;
            this.sortAscBtn.classList.toggle('active-comment-sort', savedSort === 'asc');
            this.sortDescBtn.classList.toggle('active-comment-sort', savedSort === 'desc');
        }
        if (savedFilter) {
            this.currentFilter = savedFilter;
            this.filterSelect.value = savedFilter;
        }
    }

    saveSettings() {
        const incidentId = this.container.dataset.incidentId || 'global';
        localStorage.setItem(`cw-sort-${incidentId}`, this.currentSort);
        localStorage.setItem(`cw-filter-${incidentId}`, this.currentFilter);
    }

    initCharCounter() {
        this.charCount.className = 'cw-char-count';
        this.charCount.textContent = `0 / ${this.MAX_LENGTH}`;
        
        // Находим контейнер действий
        const actionsContainer = document.querySelector('.cw-form-actions');
        
        // Добавляем элемент в DOM один раз, если его там еще нет
        if (actionsContainer && !actionsContainer.contains(this.charCount)) {
            // Вставляем сразу после span ошибки (или в начало, если ошибки нет)
            // Логика: Ошибка -> Счетчик -> Кнопки
            const errorMsg = document.getElementById('cw-error-msg');
            if (errorMsg && errorMsg.parentNode === actionsContainer) {
                actionsContainer.insertBefore(this.charCount, errorMsg.nextSibling);
            } else {
                // Если ошибки нет или она не в этом контейнере, ставим в начало
                actionsContainer.prepend(this.charCount);
            }
        }
        
        this.inputEl.addEventListener('input', () => {
            const text = this.inputEl.value;
            let currentLen = text.length;
            
            // Если превышен лимит - обрезаем текст ПЕРВЫМ делом
            if (currentLen > this.MAX_LENGTH) {
                this.inputEl.value = text.slice(0, this.MAX_LENGTH);
                currentLen = this.MAX_LENGTH; 
                
                // Добавляем класс ошибки
                this.charCount.classList.add('cw-char-error');
                
                // Блокируем кнопку
                this.submitBtn.disabled = true;
            } else {
                // Убираем класс ошибки
                this.charCount.classList.remove('cw-char-error');
                
                // Логика блокировки кнопки
                this.submitBtn.disabled = !text.trim();
            }
            
            // Обновляем текст счетчика
            this.charCount.textContent = `${currentLen} / ${this.MAX_LENGTH}`;
        });
    }

    createCustomModal() {
        if (document.getElementById('custom-delete-modal')) return;

        const modalOverlay = document.createElement('div');
        modalOverlay.id = 'custom-delete-modal-overlay';
        modalOverlay.className = 'cw-modal-overlay';

        const modalBox = document.createElement('div');
        modalBox.id = 'custom-delete-modal';
        modalBox.className = 'cw-modal-box';

        modalBox.innerHTML = `
            <div class="cw-modal-body">
                Вы уверены, что хотите удалить этот комментарий?
            </div>
            <div class="cw-modal-footer">
                <button type="button" class="btn btn-secondary cw-modal-cancel">Отмена</button>
                <button type="button" class="btn btn-danger cw-modal-confirm">Удалить</button>
            </div>
        `;

        modalOverlay.appendChild(modalBox);
        document.body.appendChild(modalOverlay);

        const closeModal = () => {
            modalOverlay.classList.remove('active-modal-comment');
            this.deletePendingId = null;
        };

        modalOverlay.querySelector('.cw-modal-cancel').addEventListener('click', closeModal);
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) closeModal();
        });

        modalOverlay.querySelector('.cw-modal-confirm').addEventListener('click', () => {
            if (this.deletePendingId) {
                this.emitAction('delete', { id: this.deletePendingId });
                closeModal();
            }
        });

        this.customModal = modalOverlay;
    }

    initListeners() {
        this.sortAscBtn.addEventListener('click', () => {
            this.setSort('asc');
            this.saveSettings();
        });
        this.sortDescBtn.addEventListener('click', () => {
            this.setSort('desc');
            this.saveSettings();
        });

        this.filterSelect.addEventListener('change', (e) => {
            this.currentFilter = e.target.value;
            this.saveSettings();
            this.renderList();
        });

        this.submitBtn.addEventListener('click', () => {
            const content = this.inputEl.value.trim();
            const editId = this.editIdInput.value;
            if (!content || content.length > this.MAX_LENGTH) return;
            if (editId) {
                this.emitAction('update', { id: parseInt(editId), content });
                this.resetForm();
            } else {
                this.emitAction('create', { content });
                this.resetForm();
            }
        });

        if (this.cancelBtn) {
            this.cancelBtn.addEventListener('click', () => {
                this.resetForm();
            });
        }
    }

    updateData(newComments) {
        this.rawComments = [...newComments];
        this.renderList();
    }

    handleUpdate(action, payload) {
        const payloadId = parseInt(payload?.id);
        if (action === 'delete') {
            if (!payloadId) return;
            
            console.log(`[UI] Attempting to delete ID: ${payloadId}`);
            const initialLen = this.rawComments.length;
            this.rawComments = this.rawComments.filter(c => parseInt(c.id) !== payloadId);
            
            if (this.rawComments.length === initialLen) {
                console.warn('[UI] Delete failed: Comment ID', payloadId);
            } else {
                console.log(`[UI] Successfully deleted comment ID ${payloadId}`);
            }
        } else if (action === 'created' || action === 'updated') {
            let existingAvatar = null;
            if (action === 'updated') {
                const oldComment = this.rawComments.find(c => parseInt(c.id) === payloadId);
                if (oldComment && oldComment.avatar_url) {
                    existingAvatar = oldComment.avatar_url;
                }
            }
            if (existingAvatar && !payload.avatar_url) {
                payload.avatar_url = existingAvatar;
            }
            const index = this.rawComments.findIndex(c => parseInt(c.id) === payloadId);
            
            if (index > -1) {
                this.rawComments[index] = payload;
            } else {
                this.rawComments.push(payload);
            }
        }
        
        this.renderList();
    }

    setSort(order) {
        this.currentSort = order;
        this.sortAscBtn.classList.toggle('active-comment-sort', order === 'asc');
        this.sortDescBtn.classList.toggle('active-comment-sort', order === 'desc');
        this.renderList();
    }

    renderList() {
        let filtered = this.rawComments;
        if (this.currentFilter === 'my') {
            filtered = filtered.filter(c => c.is_my_comment === true);
        } else if (this.currentFilter === 'others') {
            filtered = filtered.filter(c => c.is_my_comment !== true);
        }
        const sorted = [...filtered].sort((a, b) => {
            const dateA = new Date(a.created_at);
            const dateB = new Date(b.created_at);
            return this.currentSort === 'asc' ? dateA - dateB : dateB - dateA;
        });
        this.listEl.innerHTML = '';
        
        if (sorted.length === 0) {
            this.emptyEl.style.display = 'flex';
            return;
        }
        this.emptyEl.style.display = 'none';
        sorted.forEach(comment => {
            const el = this.createCommentElement(comment);
            this.listEl.appendChild(el);
        });
    }

    createCommentElement(comment) {
        const div = document.createElement('div');
        div.className = 'cw-comment-item';
        
        if (comment.is_my_comment) {
            div.classList.add('my-comment');
        } else {
            div.classList.add('other-comment');
        }
        const dateStr = new Date(comment.created_at).toLocaleString('ru-RU', {
            day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
        });
        
        let avatarHtml = '';
        const profileUrl = `/users/${comment.author_id}/`;
        
        if (comment.avatar_url) {
            avatarHtml = `<a href="${profileUrl}" class="cw-avatar-link">
                            <img src="${comment.avatar_url}" class="cw-avatar" alt="${this.escapeHtml(comment.author)}">
                          </a>`;
        } else {
            avatarHtml = `<a href="${profileUrl}" class="cw-avatar-link">
                            <div class="cw-avatar cw-avatar-placeholder">${comment.username ? comment.username.charAt(0).toUpperCase() : '?'}</div>
                          </a>`;
        }
        
        const authorText = `<span class="cw-author-name">${this.escapeHtml(comment.author)}</span>`;
        const hasEditRights = comment.can_edit === true; 
        let actionsHtml = '';
        if (hasEditRights) {
            actionsHtml += `<button class="cw-btn-edit" data-id="${comment.id}"><i class='bx bx-pencil'></i></button>`;
            actionsHtml += `<button class="cw-btn-delete" data-id="${comment.id}"><i class='bx bx-trash'></i></button>`;
        }
        div.innerHTML = `
            <div class="cw-comment-header">
                <div class="cw-author-info">
                    ${avatarHtml}
                    <div class="cw-author-text">
                        <span class="cw-role badge bg-secondary">${this.escapeHtml(comment.author_role)}</span>
                        ${authorText}
                    </div>
                </div>
                <span class="cw-date">${dateStr}</span>
                <div class="cw-actions">
                    ${actionsHtml}
                </div>
            </div>
            <div class="cw-comment-body">
                ${this.escapeHtml(comment.content)}
            </div>
        `;
        
        const editBtn = div.querySelector('.cw-btn-edit');
        if (editBtn) {
            editBtn.addEventListener('click', () => this.startEdit(comment));
        }
        
        const deleteBtn = div.querySelector('.cw-btn-delete');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deletePendingId = comment.id;
                if (this.customModal) {
                    this.customModal.classList.add('active-modal-comment');
                }
            });
        }
        return div;
    }

    startEdit(comment) {
        this.inputEl.value = comment.content;
        this.editIdInput.value = comment.id;
        this.submitBtn.textContent = 'Сохранить'; // Меняем текст на "Сохранить"

        this.submitBtn.classList.add('btn-success');   // Добавляем синий стиль
        this.submitBtn.classList.remove('btn-primary'); // Убираем зеленый стиль
        
        // Показываем кнопку отмены (убираем класс скрытия)
        if (this.cancelBtn) {
            this.cancelBtn.classList.remove('hidden');
        }
        
        this.submitBtn.disabled = false; // Активируем кнопку сохранения
        this.inputEl.focus();
        
        setTimeout(() => {
            this.container.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }, 100);
    }

    resetForm() {
        this.inputEl.value = '';
        this.editIdInput.value = '';
        this.submitBtn.textContent = 'Отправить'; // Возвращаем текст "Отправить"
        this.submitBtn.disabled = true; // Блокируем, пока пусто

        this.submitBtn.classList.add('btn-primary');   // Добавляем зеленый стиль
        this.submitBtn.classList.remove('btn-success'); // Убираем синий стиль
        
        // Скрываем кнопку отмены (добавляем класс скрытия)
        if (this.cancelBtn) {
            this.cancelBtn.classList.add('hidden');
        }
        
        // Сброс счетчика символов
        if (this.charCount) {
            this.charCount.textContent = `0 / ${this.MAX_LENGTH}`;
            this.charCount.classList.remove('cw-char-error');
        }
    }

    emitAction(action, payload) {
        if (this.onActionTriggered) {
            this.onActionTriggered(action, payload);
        }
    }

    showError(message) {
        const container = document.querySelector('.messages-container');
        if (!container) return;
        container.innerHTML = '';
        const alertDiv = document.createElement('div');
        alertDiv.className = 'message alert-error';
        alertDiv.textContent = message;
        container.appendChild(alertDiv);
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }

    escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}