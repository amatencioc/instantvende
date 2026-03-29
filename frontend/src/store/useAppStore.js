import { create } from 'zustand'

const useAppStore = create((set) => ({
  sidebarOpen: window.innerWidth >= 1024,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  notifications: [],
  addNotification: (notif) =>
    set((s) => ({ notifications: [notif, ...s.notifications].slice(0, 50) })),
}))

export default useAppStore
