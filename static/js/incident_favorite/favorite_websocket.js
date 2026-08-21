import { FavoriteConstants } from './favorite_constants.js';
import { FavoriteCore } from './favorite_core.js';

const connections = new Map();

export const FavoriteWebSocket = (() => {

  function ensureConnected(incidentId) {
    if (connections.has(incidentId)) return;
    if (connections.size >= FavoriteConstants.MAX_WS_CONNECTIONS) return;
    _open(incidentId);
  }

  function connectMany(ids) {
    ids.forEach((id) => ensureConnected(id));
  }

  function disconnect(incidentId) {
    const conn = connections.get(incidentId);
    if (!conn) return;
    conn.shouldReconnect = false;
    conn.queue = [];
    if (conn.ws) {
      conn.ws.onclose = null;
      conn.ws.close();
      conn.ws = null;
    }
    connections.delete(incidentId);
  }

  function disconnectAll() {
    connections.forEach((_, id) => disconnect(id));
  }

  function sendToggle(incidentId, isFavorite) {
    _enqueue(incidentId, {
      type: FavoriteConstants.MSG.TOGGLE,
      is_favorite: isFavorite,
    });
  }

  function sendSetPriority(incidentId, priority) {
    _enqueue(incidentId, {
      type: FavoriteConstants.MSG.SET_PRIORITY,
      priority,
    });
  }

  function isConnected(incidentId) {
    const conn = connections.get(incidentId);
    return conn !== undefined && conn.ws?.readyState === WebSocket.OPEN;
  }

  // ─── Private ─────────────────────────────────────────────────

  function _enqueue(incidentId, payload) {
    const conn = connections.get(incidentId);
    if (!conn) {
      console.warn(`[FavWS] no conn (${incidentId}), dropped`);
      return;
    }
    if (conn.ws && conn.ws.readyState === WebSocket.OPEN) {
      conn.ws.send(JSON.stringify(payload));
    } else {
      conn.queue.push(payload);
    }
  }

  function _open(incidentId) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}${FavoriteConstants.WS_BASE}${incidentId}/`;

    const ws = new WebSocket(url);
    const conn = { ws, reconnectAttempts: 0, shouldReconnect: true, queue: [] };
    connections.set(incidentId, conn);

    ws.onopen = () => {
      conn.reconnectAttempts = 0;
      _flushQueue(incidentId);
    };

    ws.onmessage = (event) => {
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      _onMessage(incidentId, data);
    };

    ws.onclose = (event) => {
      conn.ws = null;
      if (conn.shouldReconnect) _reconnect(incidentId);
    };

    ws.onerror = () => {};
  }

  function _flushQueue(incidentId) {
    const conn = connections.get(incidentId);
    if (!conn || !conn.ws || conn.ws.readyState !== WebSocket.OPEN) return;
    while (conn.queue.length) {
      conn.ws.send(JSON.stringify(conn.queue.shift()));
    }
  }

  function _onMessage(incidentId, data) {
    const { MSG_SERVER } = FavoriteConstants;
    switch (data.type) {
      case MSG_SERVER.STATE_UPDATE:
        FavoriteCore.applyExternalState(data.incident_id, {
          isFavorite: data.is_favorite,
          priority: data.priority,
        });
        break;
      case MSG_SERVER.ERROR:
        console.error(`[FavWS] error (${incidentId}):`, data.message);
        break;
    }
  }

  function _reconnect(incidentId) {
    const conn = connections.get(incidentId);
    if (!conn || !conn.shouldReconnect) return;

    const { WS_MAX_RECONNECT, WS_BASE_DELAY_MS } = FavoriteConstants;
    if (conn.reconnectAttempts >= WS_MAX_RECONNECT) return;

    conn.reconnectAttempts++;
    const delay = WS_BASE_DELAY_MS * conn.reconnectAttempts;
    setTimeout(() => {
      connections.delete(incidentId);
      _open(incidentId);
    }, delay);
  }

  return Object.freeze({
    ensureConnected,
    connectMany,
    disconnect,
    disconnectAll,
    sendToggle,
    sendSetPriority,
    isConnected,
  });
})();