// static/js/comments/main.js
import { CommentWebSocket } from '/js/comments/ws.js';
import { CommentsUI } from '/js/comments/ui.js';

document.addEventListener('DOMContentLoaded', () => {
    const configEl = document.getElementById('cw-config');
    
    if (!configEl) return;

    const incidentId = configEl.dataset.incidentId;
    const wsUrl = configEl.dataset.wsUrl;
    const currentUserId = configEl.dataset.currentUser;

    const ui = new CommentsUI('comments-widget', configEl);
    const ws = new CommentWebSocket(incidentId, wsUrl, currentUserId);

    ui.onActionTriggered = (action, payload) => {
        ws.sendMessage(action, payload);
    };

    ws.onHistoryReceived = (data) => {
        ui.updateData(data);
    };

    ws.onUpdateReceived = (action, payload) => {
        ui.handleUpdate(action, payload);
    };

    // ВАЖНО: Подключаем вывод ошибок
    ws.onErrorReceived = (msg) => {
        ui.showError(msg);
    };

    ws.connect();
});