import { useEffect, useState } from 'react'
import LiveDeliveryTable from './components/LiveDeliveryTable'
import DispatchCreatorModal from './components/DispatchCreatorModal'
import TelemetryLogFeed from './components/TelemetryLogFeed'
import { createDelivery, fetchDeliveries } from './services/api'

const STATUS_MAP = {
  PENDING: 'pending',
  LOCATION_VERIFIED: 'verified',
  OTP_SENT: 'en_route',
  COMPLETED: 'verified',
  FAILED: 'mismatch',
  CANCELLED: 'pending',
}

function normalizeDelivery(delivery) {
  const status = STATUS_MAP[delivery.status] || 'pending'

  return {
    id: String(delivery.id ?? delivery.tracking_number ?? delivery.delivery_code ?? 'N/A'),
    agent: delivery.agent_name || 'Unassigned agent',
    phone: delivery.agent_phone || delivery.buyer_phone || '',
    destination: delivery.destination_zone || delivery.zone_name || 'Unknown zone',
    cellTower: delivery.destination_cell_tower_id || delivery.destination_tower_id || 'N/A',
    status,
    eta: delivery.completed_at ? 'Delivered' : 'Live',
    distance: delivery.delivery_fee ? `${delivery.delivery_fee} KES` : '—',
  }
}

function App() {
  const [modalOpen, setModalOpen] = useState(false)
  const [deliveries, setDeliveries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadDeliveries = async () => {
      try {
        setLoading(true)
        const apiDeliveries = await fetchDeliveries()
        setDeliveries(apiDeliveries.map(normalizeDelivery))
        setError('')
      } catch (err) {
        setError(err.message || 'Unable to load deliveries')
      } finally {
        setLoading(false)
      }
    }

    loadDeliveries()
  }, [])

  const handleCreateDispatch = async (newDispatch) => {
    try {
      const payload = {
        buyer_name: newDispatch.buyerName || 'Buyer',
        buyer_phone: newDispatch.agentPhone,
        agent_name: newDispatch.agentName,
        agent_phone: newDispatch.agentPhone,
        destination_zone: newDispatch.destination,
        destination_tower_id: newDispatch.cellTower,
        destination_cell_tower_id: newDispatch.cellTower,
        payout_amount: 50,
        currency: 'KES',
      }

      const createdDelivery = await createDelivery(payload)
      const next = normalizeDelivery(createdDelivery)
      setDeliveries((prev) => [next, ...prev])
      setError('')
    } catch (err) {
      setError(err.message || 'Unable to create dispatch')
      return
    }

    setModalOpen(false)
  }

  return (
    <div className="min-h-screen bg-sp-bg text-sp-text">
      {/* Top Navigation */}
      <nav className="border-b border-sp-border bg-sp-bg/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-sp-purple rounded-lg flex items-center justify-center text-white font-bold text-lg">
                SP
              </div>
              <span className="font-bold text-lg text-sp-text-dark tracking-tight">
                SignalProof Admin
              </span>
            </div>
            <div className="flex items-center gap-4">
              <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-sp-border bg-sp-bg text-sm font-medium">
                <span className="w-2 h-2 rounded-full bg-sp-success"></span>
                <span className="text-sp-text-dark">System Online</span>
              </div>
              <button
                onClick={() => setModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-sp-purple hover:bg-sp-purple-dark rounded-lg transition-colors"
              >
                + New Dispatch
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading && deliveries.length === 0 && (
          <div className="mb-4 rounded-lg border border-sp-border bg-sp-bg px-4 py-3 text-sm text-sp-muted">
            Loading deliveries…
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: Live Delivery Table */}
          <div className="lg:col-span-2">
            <LiveDeliveryTable initialDeliveries={deliveries} />
          </div>

          {/* Right Column: Telemetry Log Feed */}
          <div className="flex flex-col gap-8">
            <TelemetryLogFeed />
            <div className="flex-1"></div>
          </div>
        </div>
      </main>

      {/* Dispatch Creator Modal */}
      <DispatchCreatorModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreate={handleCreateDispatch}
      />
    </div>
  )
}

export default App
