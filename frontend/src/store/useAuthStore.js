import { create } from 'zustand'

const useAuthStore = create((set) => ({
  apiKey: localStorage.getItem('iv_api_key') || '',
  setApiKey: (key) => {
    localStorage.setItem('iv_api_key', key)
    set({ apiKey: key })
  },
  logout: () => {
    localStorage.removeItem('iv_api_key')
    set({ apiKey: '' })
  },
}))

export default useAuthStore
