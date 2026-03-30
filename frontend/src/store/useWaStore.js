import { create } from 'zustand'

const useWaStore = create((set) => ({
  connected: null,   // null = desconocido, true = conectado, false = desconectado
  info: null,        // { pushname, phone, platform }
  qrDataUrl: null,   // data URL de imagen PNG del QR

  setStatus: (data) => set({
    connected: data.connected ?? false,
    info: data.info ?? null,
    qrDataUrl: data.qrDataUrl ?? null,
  }),
}))

export default useWaStore
