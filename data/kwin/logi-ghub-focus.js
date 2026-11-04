// logi-ghub-linux: tell the daemon which window has focus.
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

function send() {
    const w = workspace.activeWindow;
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
