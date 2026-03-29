const { app, BrowserWindow, Tray, Menu, globalShortcut, screen, ipcMain, nativeImage } = require('electron')
const Store = require('electron-store')
const path = require('path')

const store = new Store()

let tray = null
let overlayWindow = null
let settingsWindow = null
let isOverlayVisible = false

function createOverlay() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize

  const overlayHeight = Math.round(height * 0.55)
  const overlayY = height - overlayHeight

  overlayWindow = new BrowserWindow({
    width: 400,
    height: overlayHeight,
    x: width - 400,
    y: overlayY,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  overlayWindow.loadFile(path.join(__dirname, 'overlay.html'))
  overlayWindow.hide()

  overlayWindow.on('blur', () => {
    if (isOverlayVisible) hideOverlay()
  })
}

function createSettings() {
  if (settingsWindow) {
    settingsWindow.focus()
    return
  }

  settingsWindow = new BrowserWindow({
    width: 500,
    height: 480,
    resizable: false,
    title: 'Configuración — HALeph',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  settingsWindow.loadFile(path.join(__dirname, 'settings.html'))
  settingsWindow.on('closed', () => { settingsWindow = null })
}

function showOverlay() {
  overlayWindow.show()
  overlayWindow.focus()
  overlayWindow.webContents.send('overlay-opened')
  isOverlayVisible = true
}

function hideOverlay() {
  overlayWindow.hide()
  isOverlayVisible = false
}

function toggleOverlay() {
  if (isOverlayVisible) {
    hideOverlay()
  } else {
    showOverlay()
  }
}

app.whenReady().then(() => {
  const icon = nativeImage.createEmpty()
  tray = new Tray(icon)

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Abrir overlay (Ctrl+Shift+Space)', click: toggleOverlay },
    { label: 'Configuración', click: createSettings },
    { type: 'separator' },
    { label: 'Salir', click: () => app.quit() }
  ])

  tray.setToolTip('HALeph — AI Orchestrator')
  tray.setContextMenu(contextMenu)
  tray.on('click', toggleOverlay)
  tray.on('double-click', toggleOverlay)

  createOverlay()
  setTimeout(() => showOverlay(), 1000)

  globalShortcut.register('CommandOrControl+Shift+Space', toggleOverlay)

  ipcMain.on('hide-overlay', hideOverlay)
  ipcMain.on('open-settings', createSettings)

  ipcMain.handle('get-settings', () => {
    return {
      backendUrl: store.get('backendUrl', ''),
      jiraDomain: store.get('jiraDomain', ''),
      teamMembers: store.get('teamMembers', [])
    }
  })

  ipcMain.handle('save-settings', (_, settings) => {
    store.set('backendUrl', settings.backendUrl)
    store.set('jiraDomain', settings.jiraDomain)
    store.set('teamMembers', settings.teamMembers)
    return true
  })
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
})

app.on('window-all-closed', (e) => {
  e.preventDefault()
})
