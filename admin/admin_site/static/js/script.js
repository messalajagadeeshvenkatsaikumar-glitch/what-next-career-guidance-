document.addEventListener('DOMContentLoaded', function () {
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(function (item) {
        setTimeout(function () {
            item.style.opacity = '0';
            setTimeout(function () {
                item.remove();
            }, 400);
        }, 5000);
    });
});
