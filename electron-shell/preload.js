const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('gordon', {
  // renderer -> main: toggle click-through based on whether the card is showing
  setInteractive: (on) => ipcRenderer.send('overlay:interactive', on),
  // renderer -> main: open the Kitchen dashboard window
  openKitchen: () => ipcRenderer.send('overlay:open-kitchen'),
  // main -> renderer: a scored prompt is ready — render this verdict and pop up
  onVerdict: (cb) => ipcRenderer.on('gordon:verdict', (_e, verdict) => cb(verdict)),
});
