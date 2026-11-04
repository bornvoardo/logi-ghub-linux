// logi-ghub-linux: tell the daemon which window has focus, and which windows exist.
//
// Wayland does not let a normal program read the focused window, but a KWin script
// can. This one lives in KWin's scripting engine for as long as the session lasts:
// logi-ghubd loads it with org.kde.kwin.Scripting.loadScript and never writes it to
// KWin's own configuration.
//
// KWin scripts cannot register a D-Bus service, so the traffic goes the other way:
// every focus change calls a method on the service logi-ghubd already owns.

const SERVICE = 'org.logi_ghub.Focus';
const PATH = '/Focus';
const IFACE = 'org.logi_ghub.Focus';

// The app's window picker needs the windows that are open now. A KWin script
// cannot answer a D-Bus call, so the list is pushed with every focus change and the
// daemon keeps the last one; the app reads it from there.
// Fields are separated by \u0001 and windows by \u0002; neither can appear in a
// window class or a caption.
function reportWindows() {
    const out = [];
    const seen = {};
    const list = workspace.windowList ? workspace.windowList() : [];
    for (let i = 0; i < list.length; i++) {
        const w = list[i];
        if (!w) continue;
        let cls = '';
        try { cls = w.resourceClass ? String(w.resourceClass) : ''; } catch (e) {}
        if (!cls) { try { cls = w.windowClass ? String(w.windowClass) : ''; } catch (e) {} }
        if (!cls) continue;
        let desktop = '';
        try { desktop = w.desktopFileName ? String(w.desktopFileName) : ''; } catch (e) {}
        let caption = '';
        try { caption = w.caption ? String(w.caption) : ''; } catch (e) {}
        const key = cls + '\u0000' + caption;
        if (seen[key]) continue;
        seen[key] = true;
        out.push(cls + '\u0001' + caption + '\u0001' + desktop);
    }
    callDBus(SERVICE, PATH, IFACE, 'windowsReported', out.join('\u0002'));
}

function send() {
    const w = workspace.activeWindow;
    reportWindows();
    if (!w) {
        callDBus(SERVICE, PATH, IFACE, 'focusLost');
        return;
    }
    // resourceClass is the window class ("firefox"); desktopFileName is the
    // .desktop name the application set for itself, and is more reliable when set.
    callDBus(SERVICE, PATH, IFACE, 'focusChanged',
             w.resourceClass || '',
             w.caption || '',
             w.desktopFileName || '');
}

workspace.windowActivated.connect(send);

// The script is loaded after the first window is already focused, so report the
// current one instead of waiting for the next switch.
send();
