/* Recovery also works when the custom dashboard is suspended or unloaded. */
(function () {
    var onDash = location.pathname === '/3rd/html5/php/dash/index.html';
    // TPM206E: the DLNA entry point is the content browser; storage is shared with the dashboard.
    if (!onDash && location.pathname !== '/3rd/html5/php/ContentBrowser/content_browser.html') return;
    var backup = localStorage.getItem('compact-home.stock-menu.v1');
    localStorage.removeItem('compact-home.enabled.v1');
    if (backup) {
        var menu = JSON.parse(backup);
        if (!menu || !Array.isArray(menu.item)) throw new Error('Invalid stock menu backup');
        localStorage.setItem('IHSMenuItems', backup);
        if (localStorage.getItem('IHSMenuItems') !== backup) throw new Error('Stock menu restore verification failed');
        if (onDash) window.menu_info_tpv = menu;
    }
    localStorage.removeItem('compact-home.runtime.v1');
    localStorage.removeItem('compact-home.stock-menu.v1');
    try {var svc = getTvJspService(); (svc.tvServices || svc).advMsg('smallAdv', 'SEND_EVENT var s=document.getElementById("compact-home-hide-ad");if(s)s.parentNode.removeChild(s);');} catch(e) {}
    var image = new Image(); window.__nhRestoreReport = image;
    image.src = window.__nativeHomeRestoreBase + '/event?data=' + encodeURIComponent(JSON.stringify({event:'stock-restored', menuRestored:!!backup}));
    if (onDash) setTimeout(function () {window.location.reload();}, 300);
}());
