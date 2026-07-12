const eventSource = new EventSource('/alive-reload-sse');

eventSource.addEventListener("update", async (event) => {
    if (event.data === location.pathname) {
        await loadIdiomorph();
        const response = await fetch(location.pathname);

        const newHtmlText = await response.text();
        const parser = new DOMParser();
        const newDoc = parser.parseFromString(newHtmlText, 'text/html');

        Idiomorph.morph(document.documentElement, newDoc.documentElement, {morphStyle: 'outerHTML'});
        return;
    }

    const changedUrl = new URL(event.data, location.origin).href.split('?')[0];
    const resources = performance.getEntriesByType('resource');

    const isResourceUsed = resources.some(res => {
        const resUrl = res.name.split('?')[0];
        return resUrl === changedUrl;
    });

    if (!isResourceUsed) return;

    const timestamp = Date.now();

    if (event.data.endsWith(".css")) {
        const newLink = document.createElement('link');
        newLink.rel = 'stylesheet';
        newLink.classList.add('alive-reload-css');
        newLink.dataset.originalHref = event.data;

        const url = new URL(event.data, location.origin);
        url.searchParams.set('v', timestamp);
        newLink.href = url.toString();

        newLink.onload = () => {
            document.querySelectorAll(`link[rel="stylesheet"]`).forEach(old => {
                if (old !== newLink) {
                    const oldUrl = new URL(old.getAttribute('href'), location.origin).pathname;
                    const changePath = new URL(event.data, location.origin).pathname;
                    if (oldUrl === changePath) old.remove();
                }
            });
        };
        document.head.appendChild(newLink);
    }
    else if (/\.(jpg|jpeg|png|gif|svg|webp|avif)$/i.test(event.data)) {
        const targetPath = new URL(event.data, location.origin).pathname;

        document.querySelectorAll(`img, source`).forEach(el => {
            ['src', 'srcset'].forEach(attr => {
                if (el.hasAttribute(attr)) {
                    const url = new URL(el.getAttribute(attr), location.origin);
                    if (url.pathname === targetPath) {
                        url.searchParams.set('v', timestamp);
                        el.setAttribute(attr, url.pathname + url.search);
                    }
                }
            });
        });
    }
    else {
        location.reload();
    }
});

const IDIOMORPH_SRC = "https://cdn.jsdelivr.net/npm/idiomorph@0.7.4/dist/idiomorph.min.js";

function loadIdiomorph() {
    if (typeof Idiomorph !== 'undefined') return Promise.resolve();
    
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = IDIOMORPH_SRC;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error('Unable to load Idiomorph'));
        document.head.appendChild(script);
    });
}