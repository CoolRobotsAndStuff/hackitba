const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electron', {
  hideOverlay: () => ipcRenderer.send('hide-overlay'),
  openSettings: () => ipcRenderer.send('open-settings'),
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),
  onOverlayOpened: (callback) => ipcRenderer.on('overlay-opened', callback)
})
