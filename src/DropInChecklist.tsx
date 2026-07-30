import { CheckCircle, XCircle, MinusCircle } from 'lucide-react'

const T = {
  success: '#16A34A',
  danger: '#DC2626',
  primary: '#0076CE',
  warning: '#CA8A04',
}

type DropInChecklistProps = {
  checklist: {
    package_match: boolean
    mounting_match: boolean
    pin_count_match: boolean | null
    required_specs_pass: boolean
    p2p_match?: boolean
    p2p_score?: number
    p2p_details?: any
    target_package?: string
    candidate_package?: string
    target_pins?: number | null
    candidate_pins?: number | null
    target_mounting?: string
    candidate_mounting?: string
  }
  isDropIn: boolean
  notes?: string
}

export function DropInChecklist({ checklist, isDropIn, notes }: DropInChecklistProps) {
  if (!checklist || Object.keys(checklist).length === 0) return null

  const checks = [
    {
      label: 'Package Match',
      pass: checklist.package_match,
      unknown: false,
      detail: checklist.package_match
        ? checklist.target_package || 'Same'
        : `${checklist.target_package || '?'} ≠ ${checklist.candidate_package || '?'}`,
    },
    {
      label: 'Mounting Type',
      pass: checklist.mounting_match,
      unknown: false,
      detail: checklist.mounting_match ? 'Same' : 'Different',
    },
    {
      label: 'Pin Count',
      pass: checklist.pin_count_match === true,
      unknown: checklist.pin_count_match === null || checklist.pin_count_match === undefined,
      detail:
        checklist.pin_count_match === null || checklist.pin_count_match === undefined
          ? 'Unknown'
          : checklist.pin_count_match
            ? `${checklist.target_pins} pins`
            : `${checklist.target_pins ?? '?'} ≠ ${checklist.candidate_pins ?? '?'} pins`,
    },
    {
      label: 'Required Specs',
      pass: checklist.required_specs_pass,
      unknown: false,
      detail: checklist.required_specs_pass ? 'All pass' : 'Some fail',
    },
    {
      label: 'P2P Verified',
      pass: checklist.p2p_match === true,
      unknown: checklist.p2p_score === 0 && !checklist.p2p_match,
      detail:
        checklist.p2p_match
          ? `${checklist.p2p_score}% match`
          : checklist.p2p_score != null && checklist.p2p_score > 0
            ? `${checklist.p2p_score}% — below threshold`
            : 'No pinout data extracted',
    },
  ]

  return (
    <div className="mb-3">
      <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
        Drop-In Checklist
      </p>
      <div className="grid grid-cols-5 gap-2">
        {checks.map(({ label, pass: ok, unknown, detail }) => (
          <div
            key={label}
            className="flex items-start gap-2 p-2 rounded-lg"
            style={{
              backgroundColor: unknown ? '#F8FAFC' : ok ? '#F0FDF4' : '#FEF2F2',
            }}
          >
            {unknown ? (
              <MinusCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: '#94A3B8' }} />
            ) : ok ? (
              <CheckCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: T.success }} />
            ) : (
              <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: T.danger }} />
            )}
            <div>
              <p className="text-[11px] font-medium text-slate-700">{label}</p>
              <p className="text-[10px] text-slate-500">{detail}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div
        className="mt-2 px-3 py-2 rounded-lg text-xs"
        style={{
          backgroundColor: isDropIn ? '#F0FDF4' : '#FFFBEB',
          color: isDropIn ? T.success : T.warning,
          border: `1px solid ${isDropIn ? '#BBF7D0' : '#FDE68A'}`,
        }}
      >
        {isDropIn
          ? '✓ Drop-in replacement — same package, same pins, all required specs match.'
          : notes || '⚠ Not a direct drop-in — verify package, pinout, and footprint before substitution.'}
      </div>
    </div>
  )
}