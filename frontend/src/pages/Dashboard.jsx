import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { MessageSquare, Package, ShoppingCart, TrendingUp } from 'lucide-react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { getAnalytics } from '../api/analytics.js'
import StatCard from '../components/ui/StatCard.jsx'
import Card from '../components/ui/Card.jsx'
import { SkeletonCard } from '../components/ui/Skeleton.jsx'

const STATUS_COLORS = {
  pending: '#f59e0b',
  confirmed: '#3b82f6',
  shipped: '#06b6d4',
  delivered: '#10b981',
  cancelled: '#ef4444',
}

const STATUS_LABELS = {
  pending: 'Pendiente',
  confirmed: 'Confirmado',
  shipped: 'En camino',
  delivered: 'Entregado',
  cancelled: 'Cancelado',
}

function formatPhone(phone) {
  if (!phone) return 'Sin número'
  return String(phone)
}

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Buenos días'
  if (h < 18) return 'Buenas tardes'
  return 'Buenas noches'
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getAnalytics()
      .then((r) => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const today = format(new Date(), "EEEE d 'de' MMMM", { locale: es })

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <div className="h-8 w-64 bg-slate-200 rounded-xl animate-pulse" />
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  const ordersByStatus = data?.orders_by_status || {}
  const pieData = Object.entries(ordersByStatus).map(([key, val]) => ({
    name: STATUS_LABELS[key] || key,
    value: val,
    color: STATUS_COLORS[key] || '#94a3b8',
  }))

  const topProducts = data?.top_products || []
  const recentConvs = data?.recent_conversations || []

  const confirmedRevenue = (data?.revenue_confirmed || 0) / 100

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800">
          {getGreeting()}, <span className="text-indigo-600">administrador</span>
        </h1>
        <p className="text-slate-500 text-sm mt-1 capitalize">{today}</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          icon={MessageSquare}
          label="Total Conversaciones"
          value={data?.total_conversations ?? 0}
          color="indigo"
        />
        <StatCard
          icon={ShoppingCart}
          label="Pedidos Totales"
          value={data?.total_orders ?? 0}
          color="cyan"
        />
        <StatCard
          icon={TrendingUp}
          label="Ingresos Confirmados"
          value={`S/ ${confirmedRevenue.toFixed(2)}`}
          sub="Confirmados + enviados + entregados"
          color="green"
        />
        <StatCard
          icon={Package}
          label="Productos en Stock"
          value={data?.products_in_stock ?? 0}
          color="yellow"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Pie chart */}
        <Card>
          <h2 className="text-base font-semibold text-slate-800 mb-4">Pedidos por estado</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: '#ffffff',
                    border: '1px solid #e2e8f0',
                    borderRadius: 12,
                    color: '#0f172a',
                  }}
                />
                <Legend
                  formatter={(value) => (
                    <span style={{ color: '#64748b', fontSize: 12 }}>
                      {value}
                    </span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[240px] flex items-center justify-center text-slate-400 text-sm">
              Sin datos de pedidos
            </div>
          )}
        </Card>

        {/* Bar chart */}
        <Card>
          <h2 className="text-base font-semibold text-slate-800 mb-4">Top 5 productos más vendidos</h2>
          {topProducts.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={topProducts} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={100}
                  tick={{ fill: '#64748b', fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{
                    background: '#ffffff',
                    border: '1px solid #e2e8f0',
                    borderRadius: 12,
                    color: '#0f172a',
                  }}
                />
                <Bar dataKey="units_sold" fill="#6366f1" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[240px] flex items-center justify-center text-slate-400 text-sm">
              Sin datos de ventas
            </div>
          )}
        </Card>
      </div>

      {/* Recent activity */}
      <Card>
        <h2 className="text-base font-semibold text-slate-800 mb-4">Actividad reciente</h2>
        {recentConvs.length > 0 ? (
          <div className="flex flex-col gap-2">
            {recentConvs.map((conv, i) => (
              <div
                key={conv.id ?? i}
                onClick={() => navigate(`/conversations/${conv.id}`)}
                className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-50 cursor-pointer transition-colors"
              >
                <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-sm flex-shrink-0">
                  {formatPhone(conv.phone).slice(-1)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-slate-800 text-sm font-medium">
                    {conv.customer_name || formatPhone(conv.phone)}
                  </p>
                  <p className="text-slate-400 text-xs truncate">
                    {conv.last_message || 'Sin mensajes'}
                  </p>
                </div>
                <span className="text-slate-400 text-xs flex-shrink-0">
                  {conv.last_message_at
                    ? format(new Date(conv.last_message_at), 'HH:mm')
                    : ''}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-400 text-sm text-center py-8">Sin conversaciones recientes</p>
        )}
      </Card>
    </div>
  )
}
