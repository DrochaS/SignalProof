import { useState } from 'react'

const DESTINATIONS = [
  { label: 'Westlands Zone', cellTower: 'LAC-4421/CID-8812' },
  { label: 'Kawangware Hub', cellTower: 'LAC-4421/CID-8815' },
  { label: 'Kikuyu Drop-off', cellTower: 'LAC-4430/CID-9021' },
  { label: 'Karen Zone', cellTower: 'LAC-4410/CID-8710' },
  { label: 'Thika Road Depot', cellTower: 'LAC-4450/CID-9100' },
  { label: 'Ngong Road Hub', cellTower: 'LAC-4440/CID-8950' },
]

export default function DispatchCreatorModal({ isOpen, onClose, onCreate }) {
  const [form, setForm] = useState({
    agentName: '',
    agentPhone: '',
    destination: '',
  })

  const selectedDestination = DESTINATIONS.find((d) => d.label === form.destination)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!form.agentName || !form.agentPhone || !form.destination) return
    onCreate({
      agentName: form.agentName,
      agentPhone: form.agentPhone,
      destination: form.destination,
      cellTower: selectedDestination?.cellTower || '',
    })
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative bg-sp-bg w-full max-w-md p-6 rounded-xl border border-sp-border shadow-lg">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-sp-text-dark">Create New Dispatch</h2>
          <button
            onClick={onClose}
            className="text-sp-muted hover:text-sp-text-dark transition-colors"
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-sp-text-dark mb-1.5">
              Agent Name
            </label>
            <input
              type="text"
              placeholder="e.g. James Mwangi"
              className="w-full pl-3 py-2.5 border border-sp-border rounded-lg bg-sp-bg text-sp-text-dark focus:ring-2 focus:ring-sp-purple/50 focus:border-sp-purple outline-none"
              value={form.agentName}
              onChange={(e) => setForm({ ...form, agentName: e.target.value })}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-sp-text-dark mb-1.5">
              Agent Phone
            </label>
            <input
              type="tel"
              placeholder="+254 7XX XXX XXX"
              className="w-full pl-3 py-2.5 border border-sp-border rounded-lg bg-sp-bg text-sp-text-dark focus:ring-2 focus:ring-sp-purple/50 focus:border-sp-purple outline-none"
              value={form.agentPhone}
              onChange={(e) => setForm({ ...form, agentPhone: e.target.value })}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-sp-text-dark mb-1.5">
              Delivery Destination
            </label>
            <select
              className="w-full pl-3 py-2.5 border border-sp-border rounded-lg bg-sp-bg text-sp-text-dark focus:ring-2 focus:ring-sp-purple/50 focus:border-sp-purple outline-none"
              value={form.destination}
              onChange={(e) => setForm({ ...form, destination: e.target.value })}
            >
              <option value="">Select a zone…</option>
              {DESTINATIONS.map((d) => (
                <option key={d.label} value={d.label}>
                  {d.label} ({d.cellTower})
                </option>
              ))}
            </select>
            {selectedDestination && (
              <p className="mt-1 text-xs text-sp-muted">
                Cell Tower: {selectedDestination.cellTower}
              </p>
            )}
          </div>

          <div className="pt-4 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 text-sm font-medium text-sp-muted border border-sp-border rounded-lg hover:bg-sp-bg/50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!form.agentName || !form.agentPhone || !form.destination}
              className="px-4 py-2.5 text-sm font-medium text-white bg-sp-purple hover:bg-sp-purple-dark disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              Create Dispatch
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}