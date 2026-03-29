import { useEffect, useState, useMemo } from 'react'
import { ShoppingCart } from 'lucide-react'
import toast from 'react-hot-toast'
import { getOrders, updateOrderStatus } from '../api/orders.js'
import Card from '../components/ui/Card.jsx'
import Badge from '../components/ui/Badge.jsx'
import Button from '../components/ui/Button.jsx'
import Modal from '../components/ui/Modal.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import { SkeletonCard } from '../components/ui/Skeleton.jsx'

const STATUS_LABEL = {
  pending: 'Pendiente',
  confirmed: 'Confirmado',
  shipped: 'En camino',
  delivered: 'Entregado',
  cancelled: 'Cancelado',
}

const STATUS_VARIANT = {
  pending: 'yellow',
  confirmed: 'blue',
  shipped: 'cyan',
  delivered: 'green',
  cancelled: 'red',
}

const FILTERS = [
  { id: 'all', label: 'Todos' },
  { id: 'pending', label: 'Pendientes' },
  { id: 'confirmed', label: 'Confirmados' },
  { id: 'shipped', label: 'En camino' },
  { id: 'delivered', label: 'Entregados' },
  { id: 'cancelled', label: 'Cancelados' },
]

const TRANSITIONS = {
  pending: [
    { label: 'Confirmar', next: 'confirmed', variant: 'primary' },
    { label: 'Cancelar', next: 'cancelled', variant: 'danger' },
  ],
  confirmed: [
    { label: 'Marcar en camino', next: 'shipped', variant: 'primary' },
    { label: 'Cancelar', next: 'cancelled', variant: 'danger' },
  ],
  shipped: [
    { label: 'Marcar entregado', next: 'delivered', variant: 'primary' },
  ],
  delivered: [],
  cancelled: [],
}

function maskPhone(phone) {
  if (!phone) return '****'
  const str = String(phone)
  return '****' + str.slice(-4)
}

function summarizeItems(items = []) {
  if (!items.length) return '—'
  return items
    .slice(0, 3)
    .map((i) => `${i.product_name || i.name || 'Producto'} x${i.quantity}`)
    .join(', ') + (items.length > 3 ? '...' : '')
}

export default function Orders() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [detail, setDetail] = useState(null)
  const [updating, setUpdating] = useState(null)

  const load = () => {
    setLoading(true)
    getOrders()
      .then((r) => setOrders(r.data))
      .catch(() => toast.error('Error cargando pedidos'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const filtered = useMemo(() => {
    if (filter === 'all') return orders
    return orders.filter((o) => o.status === filter)
  }, [orders, filter])

  const handleStatusChange = async (order, nextStatus) => {
    setUpdating(order.id)
    try {
      await updateOrderStatus(order.id, nextStatus)
      setOrders((prev) =>
        prev.map((o) => (o.id === order.id ? { ...o, status: nextStatus } : o))
      )
      if (detail?.id === order.id) {
        setDetail((d) => ({ ...d, status: nextStatus }))
      }
      toast.success('Estado actualizado')
    } catch {
      toast.error('Error al actualizar el estado')
    } finally {
      setUpdating(null)
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
      {/* Filter tabs */}
      <Card className="p-3">
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === f.id
                  ? 'bg-violet-600/30 text-violet-400 border border-violet-500/30'
                  : 'text-white/50 hover:text-white hover:bg-white/5'
              }`}
            >
              {f.label}
              <span className="ml-1.5 text-[10px] opacity-60">
                ({f.id === 'all' ? orders.length : orders.filter((o) => o.status === f.id).length})
              </span>
            </button>
          ))}
        </div>
      </Card>

      {/* Table */}
      <Card className="p-0 overflow-hidden">
        {filtered.length === 0 ? (
          <EmptyState
            icon={ShoppingCart}
            title="Sin pedidos"
            description="No hay pedidos con este filtro"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10">
                  {['# Pedido', 'Cliente', 'Total', 'Estado', 'Productos', 'Fecha', 'Acciones'].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-white/40 font-medium text-xs uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((order, idx) => (
                  <tr
                    key={order.id}
                    className={`border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors ${
                      idx % 2 !== 0 ? 'bg-white/[0.02]' : ''
                    }`}
                    onClick={() => setDetail(order)}
                  >
                    <td className="py-3 px-4 text-white/60 font-mono text-xs">#{order.id}</td>
                    <td className="py-3 px-4 text-white/80">{maskPhone(order.phone_number)}</td>
                    <td className="py-3 px-4 text-white font-medium">
                      S/ {((order.total || 0) / 100).toFixed(2)}
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant={STATUS_VARIANT[order.status] || 'gray'}>
                        {STATUS_LABEL[order.status] || order.status}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-white/50 text-xs max-w-[180px] truncate">
                      {summarizeItems(order.items || order.order_items)}
                    </td>
                    <td className="py-3 px-4 text-white/40 text-xs">
                      {order.created_at
                        ? new Date(order.created_at).toLocaleDateString('es-PE')
                        : '—'}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                        {(TRANSITIONS[order.status] || []).map((t) => (
                          <Button
                            key={t.next}
                            variant={t.variant}
                            loading={updating === order.id}
                            onClick={() => handleStatusChange(order, t.next)}
                            className="!text-xs !py-1 !px-2"
                          >
                            {t.label}
                          </Button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Detail modal */}
      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        title={`Pedido #${detail?.id}`}
        maxWidth="max-w-xl"
      >
        {detail && (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-white/40 text-xs">Cliente</p>
                <p className="text-white font-medium">{maskPhone(detail.phone_number)}</p>
              </div>
              <div>
                <p className="text-white/40 text-xs">Estado</p>
                <Badge variant={STATUS_VARIANT[detail.status] || 'gray'}>
                  {STATUS_LABEL[detail.status] || detail.status}
                </Badge>
              </div>
              <div>
                <p className="text-white/40 text-xs">Fecha</p>
                <p className="text-white">
                  {detail.created_at
                    ? new Date(detail.created_at).toLocaleString('es-PE')
                    : '—'}
                </p>
              </div>
              <div>
                <p className="text-white/40 text-xs">Total</p>
                <p className="text-white font-bold text-lg">
                  S/ {((detail.total || 0) / 100).toFixed(2)}
                </p>
              </div>
            </div>

            {/* Items */}
            {(detail.items || detail.order_items || []).length > 0 && (
              <div>
                <p className="text-white/50 text-xs mb-2">Productos</p>
                <div className="flex flex-col gap-2">
                  {(detail.items || detail.order_items || []).map((item, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between py-2 border-b border-white/5"
                    >
                      <div>
                        <p className="text-white text-sm">{item.product_name || item.name || 'Producto'}</p>
                        <p className="text-white/40 text-xs">
                          S/ {((item.unit_price || item.price || 0) / 100).toFixed(2)} × {item.quantity}
                        </p>
                      </div>
                      <span className="text-white font-medium">
                        S/ {(((item.unit_price || item.price || 0) * item.quantity) / 100).toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {detail.notes && (
              <div>
                <p className="text-white/40 text-xs mb-1">Notas</p>
                <p className="text-white/70 text-sm bg-white/5 p-3 rounded-xl">{detail.notes}</p>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 flex-wrap">
              {(TRANSITIONS[detail.status] || []).map((t) => (
                <Button
                  key={t.next}
                  variant={t.variant}
                  loading={updating === detail.id}
                  onClick={() => handleStatusChange(detail, t.next)}
                >
                  {t.label}
                </Button>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
