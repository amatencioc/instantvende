export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center gap-4">
      {Icon && (
        <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center">
          <Icon size={32} className="text-white/30" />
        </div>
      )}
      <div>
        <p className="text-white/70 font-medium">{title}</p>
        {description && <p className="text-white/40 text-sm mt-1">{description}</p>}
      </div>
      {action}
    </div>
  )
}
