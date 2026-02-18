document.addEventListener('DOMContentLoaded', function () {
const selects = document.querySelectorAll('.select-wrapper.status-select select');

selects.forEach(select => {
    const updateClass = () => {
    // удаляем все статусы
    select.className = ''; 
    select.classList.add('status-select'); // оставляем базовый
    // добавляем класс выбранной опции
    const selectedOption = select.options[select.selectedIndex];
    if (selectedOption && selectedOption.className) {
        select.classList.add(selectedOption.className);
    }
    };

    // обновляем сразу
    updateClass();

    // обновляем при смене
    select.addEventListener('change', updateClass);
});
});