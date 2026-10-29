import { useState } from 'react'
import LiveDeliveryTable from './components/LiveDeliveryTable'
import DispatchCreatorModal from './components/DispatchCreatorModal'
import TelemetryLogFeed from './components/TelemetryLogFeed'

function App() {
  const [modalOpen, setModalOpen] = useState(false)
  const [deliveries, setDeliveries] = useState([
    {
      id: 'DSP-001',
      agent: 'James Mwangi',
      phone: '+254 712 345 678',
      destination: 'Westlands Zone',
      cellTower: 'LAC-4421/CID-8812',
      status: 'verified',
      eta: '14:30',
      distance: '12m',
    },
    {
      id: 'DSP-002',
      agent: 'Sarah Njeri',
      phone: '+254 722 123 456',
      destination: 'Kawangware Hub',
      cellTower: 'LAC-4421/CID-8815',
      status: 'en_route',
      eta: '15:15',
      distance: '1.2km',
    },
    {
      id: 'DSP-003',
      agent: 'Peter Otieno',
      phone: '+254 733 987 654',
      destination: 'Kikuyu Drop-off',
      cellTower: 'LAC-4430/CID-9021',
      status: 'pending',
      eta: '16:00',
      distance: '3.5km',
    },
    {
      id: 'DSP-004',
      agent: 'Grace Akinyi',
      phone: '+254 741 234 567',
      destination: 'Karen Zone',
      cellTower: 'LAC-4410/CID-8710',
      status: 'verified',
      eta: '14:45',
      distance: '8m',
    },
    {
      id: 'DSP-005',
      agent: 'David Kiprotich',
      phone: '+254 755 876 543',
      destination: 'Thika Road Depot',
      cellTower: 'LAC-4450/CID-9100',
      status: 'mismatch',
      eta: '15:00',
      distance: '450m',
    },
  ])

  const handleCreateDispatch = (newDispatch) => {
    setDeliveries((prev) => [newDispatch, ...prev])
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
