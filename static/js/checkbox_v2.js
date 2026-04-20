document.addEventListener('DOMContentLoaded', function() {
    const toggles = document.querySelectorAll('.toggle-v2-wrapper');

    toggles.forEach(wrapper => {
        const checkbox = wrapper.querySelector('input[type="checkbox"]');
        
        if (!checkbox) return;

        const updateState = () => {
            if (checkbox.checked) {
                wrapper.classList.add('active');
            } else {
                wrapper.classList.remove('active');
            }
        };

        checkbox.addEventListener('change', updateState);
        updateState();
    });
});