import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, Search, Eye } from 'lucide-react'
import toast from 'react-hot-toast'
import { getConversations, toggleBot } from '../api/conversations.js'
import Card from '../components/ui/Card.jsx'
import Badge from '../components/ui/Badge.jsx'
import Button from '../components/ui/Button.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import { SkeletonCard } from '../components/ui/Skeleton.jsx'

function maskPhone(phone) {
  if (!phone) return '****'
  const str = String(phone)
  return '****' + str.slice(-4)
}

const PAGE_SIZE = 10

export default function Conversations() {
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [toggling, setToggling] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    getConversations()
      .then((r) => setConversations(r.data))
      .catch(() => toast.error('Error cargando conversaciones'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    let list = conversations
    if (search) {
      list = list.filter((c) =>
        String(c.phone_number).includes(search)
      )
    }
    if (filter === 'bot_on') list = list.filter((c) => c.bot_active)
    if (filter === 'bot_off') list = list.filter((c) => !c.bot_active)
    return list
  }, [conversations, search, filter])

  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)

  const handleToggle = async (e, conv) => {
    e.stopPropagation()
    setToggling(conv.id)
    try {
      await toggleBot(conv.id)
      setConversations((prev) =>
        prev.map((c) =>
          c.id === conv.id ? { ...c, bot_active: !c.bot_active } : c
        )
      )
      toast.success(`Bot ${conv.bot_active ? 'desactivado' : 'activado'}`)
    } catch {
      toast.error('Error al cambiar estado del bot')
    } finally {
      setToggling(null)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        {[...Array(5)].map((_, i) => <SkeletonCard key={i} />)}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <Card className="flex flex-wrap gap-4 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
          <input
            type="text"
            placeholder="Buscar por número..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            className="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-4 py-2 text-sm text-white placeholder-white/30 outline-none focus:border-violet-500 transition-all"
          />
        </div>
        <div className="flex gap-2">
          {[
            { id: 'all', label: 'Todas' },
            { id: 'bot_on', label: 'Bot activo' },
            { id: 'bot_off', label: 'Bot inactivo' },
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => { setFilter(f.id); setPage(1) }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === f.id
                  ? 'bg-violet-600/30 text-violet-400 border border-violet-500/30'
                  : 'text-white/50 hover:text-white hover:bg-white/5'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </Card>

      {/* Table */}
      <Card className="p-0 overflow-hidden">
        {paginated.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="Sin conversaciones"
            description="No hay conversaciones que coincidan con los filtros"
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/10">
                    {['Cliente', 'Estado Bot', 'Último mensaje', 'Fecha', 'Acciones'].map((h) => (
                      <th key={h} className="text-left py-3 px-4 text-white/40 font-medium text-xs uppercase tracking-wider">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {paginated.map((conv, idx) => (
                    <tr
                      key={conv.id}
                      className={`border-b border-white/5 hover:bg-white/5 transition-colors ${
                        idx % 2 !== 0 ? 'bg-white/[0.02]' : ''
                      }`}
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-600 to-cyan-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                            {maskPhone(conv.phone_number).slice(-1)}
                          </div>
                          <span className="text-white/80 font-medium">
                            {maskPhone(conv.phone_number)}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <button
                          onClick={(e) => handleToggle(e, conv)}
                          disabled={toggling === conv.id}
                          className="transition-opacity disabled:opacity-50"
                        >
                          <Badge variant={conv.bot_active ? 'green' : 'red'}>
                            {toggling === conv.id ? '...' : conv.bot_active ? '● Activo' : '○ Inactivo'}
                          </Badge>
                        </button>
                      </td>
                      <td className="py-3 px-4">
                        <p className="text-white/60 text-xs truncate max-w-[200px]">
                          {conv.last_message || '—'}
                        </p>
                      </td>
                      <td className="py-3 px-4 text-white/40 text-xs">
                        {conv.last_message_at
                          ? new Date(conv.last_message_at).toLocaleDateString('es-PE')
                          : '—'}
                      </td>
                      <td className="py-3 px-4">
                        <Button
                          variant="ghost"
                          onClick={() => navigate(`/conversations/${conv.id}`)}
                          className="!px-2 !py-1 text-xs"
                        >
                          <Eye size={14} /> Ver chat
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between p-4 border-t border-white/10">
                <span className="text-xs text-white/40">
                  {filtered.length} conversaciones · Página {page} de {totalPages}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1 text-xs rounded-lg bg-white/5 text-white/60 hover:bg-white/10 disabled:opacity-30 transition-all"
                  >
                    ← Anterior
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="px-3 py-1 text-xs rounded-lg bg-white/5 text-white/60 hover:bg-white/10 disabled:opacity-30 transition-all"
                  >
                    Siguiente →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
