import { initPanel } from './panel.js';
import { renderNotifications, addNotification, updateCount } from './notifications_render.js';
import { initActions, markRead } from './notifications_actions.js';
import { connectWS } from './ws.js';
import { initNotificationsToggle } from './notifications_toggle.js';

document.addEventListener("DOMContentLoaded", () => {
    const bell = document.getElementById("notifications-toggle");
    const panel = document.getElementById("notifications-panel");
    const list = document.getElementById("notifications-list");
    const countEl = document.getElementById("notifications-count");
    const markAllBtn = document.getElementById("notifications-mark-all");
    const hideBtn = document.getElementById("notifications-hide-panel");

    initPanel({ bell, panel, hideBtn });
    initNotificationsToggle({ bell, panel });

    const socket = connectWS({
        onMessage: (data) => {
            const markFn = (id) => markRead(socket, id);

            switch (data.type) {
                case "init":
                    renderNotifications(list, data.notifications || [], markFn, panel);
                    updateCount(countEl, data.count);
                    break;
                case "notification":
                    addNotification(list, data.notification, markFn, panel);
                    updateCount(countEl, data.count);
                    break;
                case "update":
                    renderNotifications(list, data.notifications || [], markFn, panel);
                    updateCount(countEl, data.count);
                    break;
                case "count":
                    updateCount(countEl, data.count);
                    break;
            }
        }
    });

    initActions({ markAllBtn, socket });
});