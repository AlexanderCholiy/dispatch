import { getCookie, setCookie } from './cookie.js'

export function initPanel({ bell, panel, hideBtn }) {
    // восстановление состояния панели
    if (getCookie("notifications_open") === "true") panel.style.display = "block"

    bell.onclick = () => {
        if (panel.style.display === "block") {
            panel.style.display = "none"
            setCookie("notifications_open", "false")
        } else {
            panel.style.display = "block"
            setCookie("notifications_open", "true")
        }
    }

    hideBtn.onclick = () => {
        panel.style.display = "none"
        setCookie("notifications_open", "false")
    }
}