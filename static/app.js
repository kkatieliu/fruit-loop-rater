// Progressive enhancement only - every link here is a real, working <a href>.
// If this script fails to load or errors out, the site still works exactly
// as a normal server-rendered app.

(function () {
    "use strict";

    // Swap the #fruit-content panel in place instead of a full page reload
    // when switching between Costco locations on a fruit page.
    async function handleLocationFilterClick(link) {
        const container = document.getElementById("fruit-content");
        if (!container) return false;

        try {
            const response = await fetch(link.href, { headers: { "X-Requested-With": "fetch" } });
            if (!response.ok) return false;

            const html = await response.text();
            const doc = new DOMParser().parseFromString(html, "text/html");
            const fresh = doc.getElementById("fruit-content");
            if (!fresh) return false;

            container.innerHTML = fresh.innerHTML;
            history.pushState({ fruitContent: true }, "", link.href);
            window.scrollTo({ top: container.offsetTop - 80, behavior: "smooth" });
            return true;
        } catch (err) {
            return false;
        }
    }

    document.addEventListener("click", function (e) {
        const link = e.target.closest(".location-filter a");
        if (!link) return;

        e.preventDefault();
        handleLocationFilterClick(link).then(function (swapped) {
            if (!swapped) window.location.href = link.href;
        });
    });

    window.addEventListener("popstate", function () {
        if (document.getElementById("fruit-content")) {
            window.location.reload();
        }
    });
})();
