import { create } from 'zustand'

const stored = (() => {
  try { return JSON.parse(localStorage.getItem('iv_vendor') || 'null') } catch { return null }
})()

const useVendorStore = create((set) => ({
  vendor: stored,   // { id, name, email, business_name }
  setVendor: (v) => {
    localStorage.setItem('iv_vendor', JSON.stringify(v))
    set({ vendor: v })
  },
  clearVendor: () => {
    localStorage.removeItem('iv_vendor')
    set({ vendor: null })
  },
}))

export default useVendorStore
