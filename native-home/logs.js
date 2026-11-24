/* Read the custom Home's storage log back through the DLNA page (read-only). */
(function () {
    var base = window.__nativeHomeLogsBase;
    function report(data) {
        var url = base + '/event?data=' + encodeURIComponent(JSON.stringify(data));
        try {var r = new XMLHttpRequest(); r.open('GET', url, false); r.send();}
        catch (e) {var i = new Image(); window.__nhLogsReport = i; i.src = url;}
    }
    var ihs = localStorage.getItem('IHSMenuItems') || '';
    report({event:'logs-state', page:location.pathname,
        enabled:localStorage.getItem('compact-home.enabled.v1'),
        hookRan:localStorage.getItem('compact-home.hook-ran'),
        runtimeBytes:(localStorage.getItem('compact-home.runtime.v1') || '').length,
        backupBytes:(localStorage.getItem('compact-home.stock-menu.v1') || '').length,
        menuPatched:ihs.indexOf('data-compact-home') !== -1});
    var log = [];
    try {log = JSON.parse(localStorage.getItem('compact-home.log.v1') || '[]');} catch (e) {report({event:'logs-error', message:String(e)});}
    if (!log.length) report({event:'logs-empty'});
    for (var i = 0; i < log.length; i++) report({event:'log', n:i + 1, of:log.length, entry:log[i]});
    report({event:'logs-done'});
}());
