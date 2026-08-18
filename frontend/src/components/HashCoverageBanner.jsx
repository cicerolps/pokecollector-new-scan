import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'

import { getCardHashBackfillStatus } from '../api/client'
import { useSettings } from '../contexts/SettingsContext'

// Shown inside the scanner: the local hash+OCR recognizer can only match a
// card once it has a row in card_hashes, and that bank fills in gradually
// in the background (see services/card_hash_backfill.py). Right after a
// fresh install or a sync that added a lot of new cards, some of those
// cards won't be recognizable yet — this tells the user that's expected
// and temporary, instead of leaving a "no match" unexplained.
export default function HashCoverageBanner() {
  const { t } = useSettings()

  const { data: status } = useQuery({
    queryKey: ['card-hash-backfill-status'],
    queryFn: () => getCardHashBackfillStatus().then((r) => r.data),
    refetchInterval: 30000,
    retry: false,
  })

  if (!status || !status.total_hashable || status.missing <= 0) return null

  const percent = Math.min(100, Math.round((status.hashed / status.total_hashable) * 100))

  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-brand-yellow/30 bg-brand-yellow/10 px-3 py-2 text-xs text-text-secondary">
      {status.is_running
        ? <Loader2 size={14} className="flex-shrink-0 animate-spin text-brand-yellow" />
        : <div className="flex-shrink-0 h-3.5 w-3.5 rounded-full border-2 border-brand-yellow/40 border-t-brand-yellow" />}
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-text-primary">
          {t('scanner.hashCoverageTitle').replace('{percent}', percent)}
        </p>
        <p className="mt-0.5">
          {t('scanner.hashCoverageDesc')
            .replace('{missing}', status.missing)
            .replace('{total}', status.total_hashable)}
        </p>
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-brand-yellow" style={{ width: `${percent}%` }} />
        </div>
      </div>
    </div>
  )
}
