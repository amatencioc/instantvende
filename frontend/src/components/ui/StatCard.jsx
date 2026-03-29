import { motion } from 'framer-motion'
import Card from './Card.jsx'

export default function StatCard({ icon: Icon, label, value, sub, color = 'violet' }) {
  const colors = {
    violet: 'from-violet-600/20 to-violet-600/5 text-violet-400',
    cyan: 'from-cyan-600/20 to-cyan-600/5 text-cyan-400',
    green: 'from-green-600/20 to-green-600/5 text-green-400',
    yellow: 'from-yellow-600/20 to-yellow-600/5 text-yellow-400',
  }

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      transition={{ duration: 0.2 }}
    >
      <Card className="flex items-start gap-4">
        <div
          className={`w-12 h-12 rounded-xl bg-gradient-to-br flex items-center justify-center flex-shrink-0 ${colors[color]}`}
        >
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-white/50 text-sm">{label}</p>
          <p className="text-2xl font-bold text-white mt-0.5">{value}</p>
          {sub && <p className="text-white/40 text-xs mt-1">{sub}</p>}
        </div>
      </Card>
    </motion.div>
  )
}
