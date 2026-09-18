window.addEventListener("load", function () {
    // Mobile nav toggle
    const navToggle = document.getElementById("navToggle");
    const mainNav = document.querySelector(".main-nav");
    if (navToggle && mainNav) {
        navToggle.addEventListener("click", function () {
            mainNav.classList.toggle("open");
        });
    }

    // Auto-dismiss flash messages after a few seconds
    const flashes = document.querySelectorAll(".flash");
    flashes.forEach(function (flash) {
        setTimeout(function () {
            flash.style.transition = "opacity 0.4s ease";
            flash.style.opacity = "0";
            setTimeout(function () {
                flash.remove();
            }, 400);
        }, 5000);
    });

    const splash = document.getElementById("splash-screen");
    if (splash) {
        // Keep splash screen for 2.5 seconds
        setTimeout(function () {
            splash.classList.add("hide-splash");

            // Remove splash screen after animation
            setTimeout(function () {
                splash.remove();
                const mainWebsite = document.getElementById("main-website");
                if (mainWebsite) {
                    mainWebsite.classList.remove("hidden-site");
                }
            }, 700);
        }, 2500);
    }
});
