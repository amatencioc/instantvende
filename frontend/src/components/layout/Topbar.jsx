import { useLocation } from 'react-router-dom'
import { Menu, Bell } from 'lucide-react'
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
    <header
      className="fixed top-0 right-0 left-0 h-16 z-10 flex items-center gap-4 px-6"
      style={{
        background: 'rgba(10,10,20,0.8)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      <button
        onClick={toggleSidebar}
        className="p-2 rounded-xl hover:bg-white/10 text-white/60 hover:text-white transition-colors"
      >
        <Menu size={18} />
      </button>

      <h1 className="text-base font-semibold text-white/90 flex-1">{title}</h1>

      <div className="flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
        <span className="text-xs text-white/40">API conectada</span>
      </div>
    </header>
  )
}
