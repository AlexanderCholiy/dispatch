document.addEventListener('DOMContentLoaded', () => {
const wrappers = document.querySelectorAll('.select-wrapper');

wrappers.forEach(wrapper => {
    const select = wrapper.querySelector('select');
    if (!select) return;

    // Клик по select — переключаем состояние
    select.addEventListener('pointerdown', () => {
    // закрываем все остальные
    document.querySelectorAll('.select-wrapper.open')
        .forEach(w => {
        if (w !== wrapper) w.classList.remove('open');
        });

    wrapper.classList.toggle('open');
    });

    // Когда выбрали значение — гарантированно закрываем
    select.addEventListener('change', () => {
    wrapper.classList.remove('open');
    });
});

// Клик вне select — закрываем всё
document.addEventListener('pointerdown', (e) => {
    if (!e.target.closest('.select-wrapper')) {
    document.querySelectorAll('.select-wrapper.open')
        .forEach(w => w.classList.remove('open'));
    }
});
});