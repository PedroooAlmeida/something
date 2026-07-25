const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('gordon', {
  // renderer -> main: toggle click-through based on whether the card is showing
  setInteractive: (on) => ipcRenderer.send('overlay:interactive', on),
  // renderer -> main: open the Kitchen dashboard window
  openKitchen: () => ipcRenderer.send('overlay:open-kitchen'),
  // main -> renderer: Gordon caught a bad prompt, show the verdict
  onYell: (cb) => ipcRenderer.on('gordon:yell', cb),
});
