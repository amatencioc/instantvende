export default function Skeleton({ className = '' }) {
  return (
    <div
      className={`animate-pulse bg-white/10 rounded-xl ${className}`}
    />
  )
}

export function SkeletonCard() {
  return (
    <div className="glass p-5 flex flex-col gap-3">
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-8 w-3/4" />
      <Skeleton className="h-3 w-1/3" />
    </div>
  )
}
