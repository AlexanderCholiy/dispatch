import { openPanel } from './notifications_toggle.js';

export function renderNotifications(listEl, notifications, markReadFn, panel) {
    listEl.innerHTML = "";
    notifications.forEach(n => addNotification(listEl, n, markReadFn, panel, false));
}

export function addNotification(listEl, n, markReadFn, panel, showPanel = true) {
    // Проверка на дубли
    const existing = listEl.querySelector(`.notification-item[data-id='${n.id}']`);
    if (existing) {
        removeNotification(existing);  // удаляем старый элемент
    }

    const el = document.createElement("div");
    el.classList.add("notification-item", `notification-${(n.level || 'low').toLowerCase()}`);

    const title = n.title || "Без темы";
    const message = n.message || "—";
    const sent_at = n.send_at ? new Date(n.send_at) : new Date();
    const dateStr = isNaN(sent_at.getTime()) ? "" : sent_at.toLocaleString();

    const notificationUrl = n.notification_url || null;
    const incidentUrl = n.incident_url || null;

    const titleHtml = incidentUrl
        ? `<a href="${incidentUrl}" class="notification-title">${title}</a>`
        : `<div class="notification-title">${title}</div>`;

    const messageHtml = notificationUrl
        ? `<a href="${notificationUrl}" class="notification-message">${message}</a>`
        : `<div class="notification-message">${message}</div>`;

    el.dataset.id = n.id;
    el.innerHTML = `
        ${titleHtml}
        ${messageHtml}
        <div class="notification-footer">
            <span class="notification-date">${dateStr}</span>
            <button class="btn btn-secondary notification-mark-read">Прочитано</button>
        </div>
    `;

    el.querySelector(".notification-mark-read").onclick = (e) => {
        e.stopPropagation();
        markReadFn(n.id);
        removeNotification(el);
    };

    listEl.prepend(el);  // вставляем новое уведомление в начало
    requestAnimationFrame(() => el.classList.add("show"));

    if (showPanel && n.level === "high" && panel.style.display !== "block") {
        openPanel(panel);
    }
}

export function removeNotification(el) {
    el.classList.remove("show");
    el.addEventListener("transitionend", () => el.remove(), { once: true });
}

export function updateCount(countEl, count) {
    if (count > 0) {
        countEl.innerText = count;
        countEl.style.display = "inline-block";
    } else {
        countEl.style.display = "none";
    }
}
