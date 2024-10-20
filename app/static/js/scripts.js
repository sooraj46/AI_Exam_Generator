// app/static/js/scripts.js

// Example: Confirm before deleting a user or group
document.addEventListener('DOMContentLoaded', function () {
    const deleteButtons = document.querySelectorAll('.btn-delete');

    deleteButtons.forEach(function (button) {
        button.addEventListener('click', function (e) {
            const confirmed = confirm('Are you sure you want to delete this item?');
            if (!confirmed) {
                e.preventDefault();
            }
        });
    });
});
