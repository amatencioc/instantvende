import clsx from 'clsx'

export default function Card({ children, className = '', ...props }) {
  return (
    <div
      className={clsx('bg-white border border-slate-200 rounded-xl shadow-sm p-5', className)}
      {...props}
    >
      {children}
    </div>
  )
}
