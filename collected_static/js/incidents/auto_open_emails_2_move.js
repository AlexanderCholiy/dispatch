document.addEventListener('DOMContentLoaded', () => {
// Находим все email-tree, у которых есть класс chosen
const chosenTrees = document.querySelectorAll('.email-tree.chosen');

chosenTrees.forEach(tree => {
    // Находим кнопку toggle внутри этого дерева
    const toggleBtn = tree.querySelector('.toggle-tree-btn');
    if (toggleBtn) {
    // "Нажимаем" кнопку, имитируя клик
    toggleBtn.click();
    }
});
});