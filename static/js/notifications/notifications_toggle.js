import { getCookie, setCookie } from './cookie.js';

export function initNotificationsToggle({ bell, panel }) {
    if (getCookie("notifications_open") === "true") {
        panel.style.display = "block";
        panel.classList.add("show");
    }

    bell.onclick = () => {
        if (panel.style.display === "block") {
            panel.style.display = "none";
            panel.classList.remove("show");
            setCookie("notifications_open", "false");
        } else {
            panel.style.display = "block";
            panel.classList.add("show");
            setCookie("notifications_open", "true");
        }
    }
}

export function openPanel(panel) {
    panel.style.display = "block";
    panel.classList.add("show");
    setCookie("notifications_open", "true");
}