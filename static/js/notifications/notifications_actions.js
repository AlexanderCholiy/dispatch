export function initActions({ markAllBtn, socket }) {
    markAllBtn.onclick = () => {
        const ws = socket.getSocket();
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "mark_all" }));
        } else {
            console.warn("WS not ready");
        }
    };
}

export function markRead(socket, id) {
    const ws = socket.getSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "mark_read", id }));
    } else {
        console.warn("WS not ready");
    }
}