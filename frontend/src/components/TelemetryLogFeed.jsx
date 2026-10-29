import { useState, useEffect } from 'react'

const INITIAL_LOGS = [
  { time: '14:32:11', tower: 'LAC-4421/CID-8812', event: 'Agent verified at Westlands Zone', type: 'success' },
  { time: '14:31:45', tower: 'LAC-4421/CID-8815', event: 'Agent en route to Kawangware Hub', type: 'info' },
  { time: '14:30:22', tower: 'LAC-4430/CID-9021', event: 'Tower mismatch detected — Kikuyu Drop-off', type: 'warning' },
  { time: '14:29:08', tower: 'LAC-4410/CID-8710', event: 'OTP dispatched to buyer (Karen Zone)', type: 'success' },
  { time: '14:27:55', tower: 'LAC-4450/CID-9100', event: 'Agent arrived at Thika Road Depot', type: 'info' },
  { time: '14:25:30', tower: 'LAC-4421/CID-8812', event: 'USSD handshake initiated (*384*#)', type: 'info' },
]

const TYPE_CONFIG = {
  success: { label: 'VERIFIED', color: 'text-sp-success bg-sp-success/10 border-sp-success/20' },
  info: { label: 'INFO', color: 'text-sp-purple bg-sp-purple/10 border-sp-purple/20' },
  warning: { label: 'WARNING', color: 'text-sp-warning bg-sp-warning/10 border-sp-warning/20' },
  error: { label: 'ERROR', color: 'text-sp-danger bg-sp-danger/10 border-sp-danger/20' },
}

export default function TelemetryLogFeed() {
  const [logs, setLogs] = useState(INITIAL_LOGS)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    const interval = setInterval(() => {
      setLogs((prev) => {
        const newLogs = [
          {
            time: new Date().toLocaleTimeString('en-US', { hour12: false }),
            tower: `LAC-44${Math.floor(Math.random() * 90) + 10}/CID-${Math.floor(Math.random() * 9000) + 1000}`,
            event: 'Cell-tower heartbeat — signal stable',
            type: 'info',
          },
          ...prev,
        ].slice(0, 10)
        return newLogs
      })
    }, 15000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-sp-text-dark">Telemetry Log Feed</h2>
        <label className="flex items-center gap-2 text-sm text-sp-muted cursor-pointer select-none">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded text-sp-purple focus:ring-sp-purple"
          />
          Auto-scroll
        </label>
      </div>

      <div className="flex-1 overflow-y-auto border border-sp-border rounded-lg bg-sp-bg/50 p-3 font-mono text-xs space-y-2 pr-2">
        {logs.map((log, idx) => {
          const config = TYPE_CONFIG[log.type]
          return (
            <div key={idx} className="flex items-start gap-3 animate-[fadeIn_0.2s_ease-out]">
              <span className="text-sp-muted w-24 shrink-0">{log.time}</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${config.color}`}>
                {config.label}
              </span>
              <span className="text-sp-text-dark">{log.tower}</span>
              <span className="ml-auto text-sp-text">{log.event}</span>
            </div>
          )
        })}
        {logs.length === 0 && (
          <div className="text-center text-sp-muted py-4">No telemetry events</div>
        )}
      </div>
    </div>
  )
}