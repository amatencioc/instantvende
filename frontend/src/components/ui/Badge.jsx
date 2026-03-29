import clsx from 'clsx'

const variants = {
  green: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
  yellow: 'bg-amber-100 text-amber-700 border border-amber-200',
  blue: 'bg-blue-100 text-blue-700 border border-blue-200',
  red: 'bg-red-100 text-red-600 border border-red-200',
  cyan: 'bg-cyan-100 text-cyan-700 border border-cyan-200',
  violet: 'bg-violet-100 text-violet-700 border border-violet-200',
  gray: 'bg-slate-100 text-slate-600 border border-slate-200',
}

export default function Badge({ children, variant = 'gray', className = '' }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium',
        variants[variant] || variants.gray,
        className
      )}
    >
      {children}
    </span>
  )
}
