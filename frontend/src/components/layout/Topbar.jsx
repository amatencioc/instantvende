import { useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
import useAppStore from '../../store/useAppStore.js'

const pageTitles = {
  '/dashboard': 'Dashboard',
  '/conversations': 'Conversaciones',
  '/products': 'Productos',
  '/orders': 'Pedidos',
  '/bot-profile': 'Perfil del Bot',
}

export default function Topbar() {
  const { toggleSidebar } = useAppStore()
  const location = useLocation()

  const title = Object.entries(pageTitles).find(([path]) =>
    location.pathname.startsWith(path)
  )?.[1] || 'Admin'

  return (
    <header className="fixed top-0 right-0 left-0 h-16 z-10 flex items-center gap-4 px-6 bg-white border-b border-slate-200 shadow-sm">
      <button
        onClick={toggleSidebar}
        className="p-2 rounded-xl hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
      >
        <Menu size={18} />
      </button>

      <h1 className="text-base font-semibold text-slate-800 flex-1">{title}</h1>

      <div className="flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        <span className="text-xs text-slate-600">API conectada</span>
      </div>
    </header>
  )
}
