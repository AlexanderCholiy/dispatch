// static/js/comments/ws.js

export class CommentWebSocket {
    constructor(incidentId, wsUrl, currentUserId) {
        this.incidentId = incidentId;
        this.currentUserId = parseInt(currentUserId);
        this.wsUrl = wsUrl;
        this.socket = null;
        
        this.onHistoryReceived = null;
        this.onUpdateReceived = null;
        this.onErrorReceived = null; // Коллбек для ошибок
    }

    connect() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) return;

        this.socket = new WebSocket(this.wsUrl);

        this.socket.onopen = () => {
            console.log('WS Connected');
        };

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'init_history') {
                if (this.onHistoryReceived && Array.isArray(data.data)) {
                    this.onHistoryReceived(data.data);
                }
            } else if (data.type === 'update') {
                if (this.onUpdateReceived) {
                    this.onUpdateReceived(data.action, data.payload);
                }
            } else if (data.type === 'error') {
                if (this.onErrorReceived) {
                    this.onErrorReceived(data.message);
                }
            }
        };

        this.socket.onclose = () => {
            console.log('WS Disconnected');
        };

        this.socket.onerror = (error) => {
            console.error('WS Error:', error);
            if (this.onErrorReceived) {
                this.onErrorReceived("Ошибка соединения с сервером");
            }
        };
    }

    sendMessage(action, payload) {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            console.warn('Socket not open');
            return;
        }
        const message = { action, data: payload };
        this.socket.send(JSON.stringify(message));
    }

    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }
}