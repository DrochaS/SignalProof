import { useState } from 'react'

const STATUS_LABELS = {
  verified: 'Verified',
  en_route: 'En Route',
  pending: 'Pending',
  mismatch: 'Tower Mismatch',
}

const STATUS_COLORS = {
  verified: 'bg-sp-success/10 text-sp-success border-sp-success/20',
  en_route: 'bg-sp-warning/10 text-sp-warning border-sp-warning/20',
  pending: 'bg-sp-muted/10 text-sp-muted border-sp-muted/20',
  mismatch: 'bg-sp-danger/10 text-sp-danger border-sp-danger/20',
}

export default function LiveDeliveryTable({ initialDeliveries = [] }) {
  const [deliveries, setDeliveries] = useState(initialDeliveries)
  const [search, setSearch] = useState('')

  const filtered = deliveries.filter(
    (d) =>
      d.id.toLowerCase().includes(search.toLowerCase()) ||
      d.agent.toLowerCase().includes(search.toLowerCase()) ||
      d.destination.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-sp-text-dark">Live Deliveries</h2>
          <p className="text-sm text-sp-muted">
            {filtered.length} active dispatches across cell-tower zones
          </p>
        </div>
        <div className="relative w-full md:w-72">
          <input
            type="text"
            placeholder="Search agent, destination, or tower…"
            className="w-full pl-10 pr-4 py-2.5 border border-sp-border rounded-lg bg-sp-bg text-sp-text-dark focus:ring-2 focus:ring-sp-purple/50 focus:border-sp-purple outline-none transition-all"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse border border-sp-border rounded-lg">
          <thead>
            <tr className="bg-sp-bg/50 text-sp-muted text-sm uppercase tracking-wider">
              <th className="px-4 py-3 text-left font-medium">Dispatch ID</th>
              <th className="px-4 py-3 text-left font-medium">Agent</th>
              <th className="px-4 py-3 text-left font-medium">Destination</th>
              <th className="px-4 py-3 text-left font-medium">Cell Tower</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3 text-left font-medium">ETA</th>
              <th className="px-4 py-3 text-left font-medium">Distance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-sp-border">
            {filtered.map((d) => (
              <tr
                key={d.id}
                className="bg-sp-bg hover:bg-sp-purple-light/50 transition-colors border-b border-sp-border/50 last:border-0"
              >
                <td className="px-4 py-3 text-sm font-mono text-sp-text-dark">
                  {d.id}
                </td>
                <td className="px-4 py-3 text-sm text-sp-text-dark">
                  {d.agent}
                </td>
                <td className="px-4 py-3 text-sm text-sp-text-dark">
                  {d.destination}
                </td>
                <td className="px-4 py-3 text-sm font-mono text-sp-muted">
                  {d.cellTower}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${STATUS_COLORS[d.status]}`}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                    {STATUS_LABELS[d.status]}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-sp-muted">{d.eta}</td>
                <td className="px-4 py-3 text-sm text-sp-text-dark">{d.distance}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sp-muted">
                  No deliveries found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}