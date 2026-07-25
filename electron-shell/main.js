const {
  app,
  BrowserWindow,
  globalShortcut,
  ipcMain,
  screen,
  clipboard,
} = require('electron');
const path = require('path');
const fs = require('fs');

const { scorePrompt, hasKey } = require('./scorer');

// ── Load electron-shell/.env into process.env (so ABHAY's key is picked up) ──
function loadDotEnv() {
  try {
    const raw = fs.readFileSync(path.join(__dirname, '.env'), 'utf8');
    for (const line of raw.split('\n')) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/i);
      if (m && !process.env[m[1]]) {
        process.env[m[1]] = m[2].replace(/^['"]|['"]$/g, '');
      }
    }
  } catch {
    /* no .env yet — fine, scorer falls back to mock */
  }
}
loadDotEnv();

// The Kitchen lives in a sibling folder in dev; when packaged it's copied into
// the app's resources (see electron-builder extraResources in package.json).
const KITCHEN_PAGE = app.isPackaged
  ? path.join(process.resourcesPath, 'design_handoff_gordon_overlay', 'Gordon.dc.html')
  : path.join(__dirname, '..', 'design_handoff_gordon_overlay', 'Gordon.dc.html');
const OVERLAY_PAGE = path.join(__dirname, 'overlay.html');

// Stand-in prompt used when there's nothing on the clipboard — until the capture
// teammate feeds Gordon the real submitted prompt, this is what he scores.
const SAMPLE_PROMPT = 'fix the error';

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

  overlayWin.setAlwaysOnTop(true, 'screen-saver');
  overlayWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  // Interactive by default so the card's buttons always work; the renderer asks
  // us to go click-through when the card is hidden (ipc 'overlay:interactive').
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

// Score a prompt and push the verdict to the overlay so it pops up.
async function yell(promptText) {
  if (!overlayWin || overlayWin.isDestroyed()) return;
  const verdict = await scorePrompt(promptText);
  overlayWin.webContents.send('gordon:verdict', verdict);
}

app.whenReady().then(() => {
  createOverlay();

  console.log(`[gordon] local ⌥⌘Y scorer: ${hasKey() ? 'REAL (Claude)' : 'MOCK'}. Live verdicts come from the backend WebSocket.`);

  // Open the Kitchen on launch. The overlay stays idle (invisible) until a real
  // verdict arrives over the backend WebSocket — that's the intended behaviour.
  openKitchen();

  // ⌥⌘G — open/close the Kitchen dashboard
  globalShortcut.register('CommandOrControl+Alt+G', () => {
    if (kitchenWin && kitchenWin.isVisible()) kitchenWin.hide();
    else openKitchen();
  });

  // ⌥⌘Y — DEV capture stand-in: score whatever's on the clipboard, then yell.
  // The real capture teammate replaces this trigger with actual prompt capture,
  // calling yell(capturedPrompt) — the rest of the pipeline is unchanged.
  globalShortcut.register('CommandOrControl+Alt+Y', () => {
    const text = clipboard.readText();
    yell(text || SAMPLE_PROMPT);
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createOverlay();
  });
});

// Renderer tells us when the card is visible → capture clicks; else click-through
ipcMain.on('overlay:interactive', (_e, interactive) => {
  if (!overlayWin || overlayWin.isDestroyed()) return;
  if (interactive) overlayWin.setIgnoreMouseEvents(false);
  else overlayWin.setIgnoreMouseEvents(true, { forward: true });
});

ipcMain.on('overlay:open-kitchen', () => openKitchen());

app.on('will-quit', () => globalShortcut.unregisterAll());

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
