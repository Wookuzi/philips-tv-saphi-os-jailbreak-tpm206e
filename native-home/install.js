/* Save the owner's Home UI and a reversible launcher hook in browser storage.
   The stock firmware files and app installation state are never modified.
   TPM206E: this runs on the DLNA content browser page, whose localStorage is
   shared with the Home dashboard (/3rd/html5/php/dash/index.html). The hook is
   verified to fire there when Home draws a "Reorder" tile, including after a
   cold restart. The custom Home appears the next time HOME is pressed. */
(function () {
    var config = window.__nativeHomeInstall;
    var onDash = location.pathname === '/3rd/html5/php/dash/index.html';
    if (location.protocol !== 'file:' || (!onDash && location.pathname !== '/3rd/html5/php/ContentBrowser/content_browser.html')) return;
    var prefix = 'compact-home.', backupKey = prefix + 'stock-menu.v1';
    function report(data) {
        var url = config.base + '/event?data=' + encodeURIComponent(JSON.stringify(data));
        try {var r = new XMLHttpRequest(); r.open('GET', url, false); r.send();}
        catch (e) {var image = new Image(); window.__nhInstallReport = image; image.src = url;}
    }
    try {
        var raw = localStorage.getItem('IHSMenuItems');
        var existingBackup = localStorage.getItem(backupKey);
        if (!raw) throw new Error('IHSMenuItems is missing: press HOME once and open each row, then retry.');
        if (!existingBackup && raw.indexOf('data-compact-home') !== -1)
            throw new Error('Menu is already patched but no backup exists. Refusing to overwrite.');
        var menu = JSON.parse(raw), patched = 0;
        if (!menu || !Array.isArray(menu.item)) throw new Error('Stock launcher configuration is unavailable.');
        var backup = existingBackup || raw;
        // The dashboard builds <img src="ITEMIMG"> with innerHTML (verified on
        // TPM206E), so closing the double quote adds real attributes. The handler
        // must not contain double quotes. Mask the stock document for one tick,
        // then run the saved runtime; always release the mask on failure.
        var handler = "this.onload=null;this.onerror=null;try{localStorage.setItem('compact-home.hook-ran',String(Date.now()))}catch(z){};if(localStorage.getItem('compact-home.enabled.v1')==='1'&&!window.__nhScheduled&&localStorage.getItem('compact-home.runtime.v1')){window.__nhScheduled=true;var root=document.documentElement,oldVisibility=root.style.visibility;root.style.visibility='hidden';try{var s=getTvJspService();(s.tvServices||s).advMsg('smallAdv','HIDE_WIN ')}catch(e){};setTimeout(function(){try{(0,eval)(localStorage.getItem('compact-home.runtime.v1')||'')}catch(e){window.__nhScheduled=false}finally{root.style.visibility=oldVisibility}},0)}";
        if (handler.indexOf('"') !== -1) throw new Error('Internal: handler contains a double quote.');
        menu.item.forEach(function (row) {
            (row.row2 || []).forEach(function (item) {
                if (item && item.itemName === 'Reorder' && typeof item.itemImg === 'string') {
                    var original = item.itemImg.split('" data-compact-home=')[0];
                    item.itemImg = original + '" data-compact-home="1" onload="' + handler + '" onerror="' + handler;
                    patched++;
                }
            });
        });
        if (patched < 2) throw new Error('Expected launcher anchors were not found (found ' + patched + ').');
        var patchedJson = JSON.stringify(menu);
        JSON.parse(patchedJson);
        // Send the original menu to the computer first (synchronously, so the
        // DLNA page cannot be torn down mid-install).
        var request = new XMLHttpRequest();
        request.open('POST', config.base + '/backup', false);
        request.setRequestHeader('Content-Type', 'text/plain');
        request.send(backup);
        if (request.status !== 200) throw new Error('Backup was not accepted by the computer (' + request.status + '). No hook installed.');
        try {
            localStorage.setItem(backupKey, backup);
            localStorage.setItem(prefix + 'runtime.v1', config.runtime);
            localStorage.setItem(prefix + 'enabled.v1', '1');
            localStorage.removeItem(prefix + 'log.v1');
            localStorage.removeItem(prefix + 'hook-ran');
            localStorage.setItem('IHSMenuItems', patchedJson);
            if (onDash) window.menu_info_tpv = menu;
            if (localStorage.getItem(prefix + 'runtime.v1') !== config.runtime) throw new Error('Runtime storage verification failed.');
            if (localStorage.getItem('IHSMenuItems') !== patchedJson) throw new Error('Menu storage verification failed.');
        } catch (e) {
            localStorage.removeItem(prefix + 'enabled.v1');
            localStorage.setItem('IHSMenuItems', backup);
            throw e;
        }
        report({event:'installed', anchors:patched, runtimeBytes:config.runtime.length, backupBytes:backup.length,
                storage:'localStorage', page:location.pathname});
        if (onDash) (0, eval)(config.runtime);
    } catch (e) {report({event:'install-error', message:String(e)});}
}());
