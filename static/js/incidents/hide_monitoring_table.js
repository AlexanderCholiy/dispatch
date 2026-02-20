document.addEventListener("DOMContentLoaded", function () {
    const toggleBtn = document.getElementById("monitoringToggle");
    const content = document.getElementById("monitoringContent");
    const toggleText = toggleBtn.querySelector(".toggle-text");

    const STORAGE_KEY = "monitoring_table_collapsed";

    // функция изменения состояния
    function setState(collapsed) {
        if (collapsed) {
            content.classList.add("collapsed");
            content.classList.remove("expanded");
            toggleText.textContent = "Показать мониторинг оборудования";
        } else {
            content.classList.remove("collapsed");
            content.classList.add("expanded");
            toggleText.textContent = "Скрыть мониторинг оборудования";
        }
        // сохраняем состояние в localStorage
        localStorage.setItem(STORAGE_KEY, collapsed);
    }

    // начальное состояние
    const savedState = localStorage.getItem(STORAGE_KEY) === "true";
    setState(savedState);

    // обработчик клика
    toggleBtn.addEventListener("click", function () {
        const isCollapsed = content.classList.contains("collapsed");
        setState(!isCollapsed);
    });

    // при ресайзе корректируем max-height для раскрытой таблицы
    window.addEventListener("resize", () => {
        if (content.classList.contains("expanded")) {
            content.style.maxHeight = content.scrollHeight + "px";
        }
    });
});