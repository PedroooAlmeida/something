const {
  app,
  BrowserWindow,
  globalShortcut,
  ipcMain,
  screen,
} = require('electron');
const path = require('path');

const KITCHEN_PAGE = path.join(
  __dirname,
  '..',
  'design_handoff_gordon_overlay',
  'Gordon.dc.html'
);
const OVERLAY_PAGE = path.join(__dirname, 'overlay.html');

let overlayWin = null;
let kitchenWin = null;

// ── Overlay: frameless, transparent, always-on-top, floats over everything ──
function createOverlay() {
  const { workArea } = screen.getPrimaryDisplay();
  const W = 460;
  const H = 640;

  overlayWin = new BrowserWindow({
    width: W,
    height: H,
    x: workArea.x + workArea.width - W - 12,
    y: workArea.y + workArea.height - H - 12,
    frame: false,
    transparent: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    hasShadow: false,
    focusable: true,
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
    },
  });

  // float above full-screen apps too
  overlayWin.setAlwaysOnTop(true, 'screen-saver');
  overlayWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  // Interactive by default so the card's buttons always work. When the card is
  // hidden the renderer asks us to go click-through (see ipc 'overlay:interactive').
  overlayWin.loadFile(OVERLAY_PAGE);
}

// ── Kitchen: normal window, opened only when you want the dashboard ──
function openKitchen() {
  if (kitchenWin && !kitchenWin.isDestroyed()) {
    kitchenWin.show();
    kitchenWin.focus();
    return;
  }
  kitchenWin = new BrowserWindow({
    width: 1200,
    height: 800,
    backgroundColor: '#0d0e14',
    title: 'The Kitchen',
    webPreferences: { contextIsolation: true },
  });
  kitchenWin.loadFile(KITCHEN_PAGE);
  kitchenWin.on('closed', () => (kitchenWin = null));
}

app.whenReady().then(() => {
  createOverlay();

  // Show both surfaces on launch so it's obvious the app is running:
  // open the Kitchen window, and pop Gordon's overlay after it loads.
  openKitchen();
  overlayWin.webContents.once('did-finish-load', () => {
    setTimeout(() => overlayWin.webContents.send('gordon:yell'), 1200);
  });

  // ⌥⌘G — open/close the Kitchen dashboard
  globalShortcut.register('CommandOrControl+Alt+G', () => {
    if (kitchenWin && kitchenWin.isVisible()) kitchenWin.hide();
    else openKitchen();
  });

  // ⌥⌘Y — simulate Gordon catching a bad prompt (demo trigger for the popup)
  globalShortcut.register('CommandOrControl+Alt+Y', () => {
    if (overlayWin) overlayWin.webContents.send('gordon:yell');
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createOverlay();
  });
});

// Renderer tells us when the card is visible → capture clicks; else click-through
ipcMain.on('overlay:interactive', (_e, interactive) => {
  if (!overlayWin) return;
  if (interactive) overlayWin.setIgnoreMouseEvents(false);
  else overlayWin.setIgnoreMouseEvents(true, { forward: true });
});

ipcMain.on('overlay:open-kitchen', () => openKitchen());

app.on('will-quit', () => globalShortcut.unregisterAll());

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
