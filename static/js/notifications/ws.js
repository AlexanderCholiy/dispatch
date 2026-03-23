export function connectWS({ onMessage }) {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    let socket = null;
    let heartbeatInterval = null;

    function init() {
        socket = new WebSocket(`${protocol}://${window.location.host}/ws/notifications/`);

        socket.onopen = () => {
            if (!heartbeatInterval) {
                heartbeatInterval = setInterval(() => {
                    if (socket.readyState === WebSocket.OPEN) {
                        socket.send(JSON.stringify({ action: "ping" }));
                    }
                }, 300000);
            }
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                onMessage(data);
            } catch (err) {
                console.error("WS parse error:", err);
            }
        };

        socket.onclose = () => {
            console.log("WS disconnected, reconnect in 3s");
            if (heartbeatInterval) clearInterval(heartbeatInterval);
            heartbeatInterval = null;
            setTimeout(init, 3000);
        };

        socket.onerror = (err) => {
            console.error("WS error:", err);
            socket.close();
        };
    }

    init();

    return {
        send: (data) => {
            if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(data));
        },
        getSocket: () => socket
    };
}