const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
const socketUrl = protocol + location.host + '/ws/incidents/stats/';
const socket = new WebSocket(socketUrl);

const pre = document.getElementById('stats-json');

socket.onmessage = function (event) {
    try {
        const data = JSON.parse(event.data);
        pre.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
        pre.textContent = 'Ошибка парсинга JSON';
        console.error(e);
    }
};

socket.onclose = () => {
    pre.textContent = 'WebSocket соединение закрыто';
};

socket.onerror = (e) => {
    pre.textContent = 'Ошибка WebSocket';
    console.error(e);
};