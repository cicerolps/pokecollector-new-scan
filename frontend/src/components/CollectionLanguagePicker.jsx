import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

import { useSettings } from '../contexts/SettingsContext'
import { useVisibleTcgdexLanguages } from '../hooks/useVisibleTcgdexLanguages'
import { normalizeTcgdexLanguage, tcgdexLanguageLabel } from '../utils/tcgdexLanguages'
import TcgdexLanguageSelect from './TcgdexLanguageSelect'

function parseShortlist(raw) {
  return (raw || '')
    .split(',')
    .map((code) => code.trim())
    .filter(Boolean)
}

// Quick-select buttons for the trainer's primary + frequently-used card
// languages (Settings → Appearance → Collection Languages), so adding a
// card doesn't default to opening a dropdown of every TCGdex language.
// Falls back to whatever languages are currently synced when the trainer
// hasn't set a shortlist yet, and always offers the full picker for the
// rare card outside the shortlist.
export default function CollectionLanguagePicker({ value, onChange, className = '' }) {
  const { settings, t } = useSettings()
  const visibleLanguages = useVisibleTcgdexLanguages()
  const [expanded, setExpanded] = useState(false)

  const primary = normalizeTcgdexLanguage(settings.collection_language_primary || settings.language || 'en')
  let shortlist = parseShortlist(settings.collection_language_shortlist)
  if (!shortlist.length) {
    shortlist = visibleLanguages.map((language) => language.code).filter((code) => code !== primary).slice(0, 3)
  }
  const quickCodes = [primary, ...shortlist.filter((code) => code !== primary)]

  const normalizedValue = normalizeTcgdexLanguage(value)
  const valueInQuickList = quickCodes.includes(normalizedValue)
  const showFullPicker = expanded || !valueInQuickList

  return (
    <div className={className}>
      <div className="flex flex-wrap gap-1.5">
        {quickCodes.map((code) => {
          const selected = normalizedValue === code
          return (
            <button
              key={code}
              type="button"
              onClick={() => onChange(code)}
              className={`rounded-lg border px-2.5 py-1.5 text-xs font-semibold transition-colors ${
                selected
                  ? 'border-brand-red bg-brand-red text-white'
                  : 'border-border bg-bg-card text-text-secondary hover:text-text-primary'
              }`}
            >
              {tcgdexLanguageLabel(code, { full: true })}
            </button>
          )
        })}
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="flex items-center gap-1 rounded-lg border border-border bg-bg-card px-2.5 py-1.5 text-xs font-semibold text-text-muted transition-colors hover:text-text-primary"
          aria-expanded={showFullPicker}
        >
          {t('lang.moreLanguages')}
          <ChevronDown size={12} className={`transition-transform ${showFullPicker ? 'rotate-180' : ''}`} />
        </button>
      </div>
      {showFullPicker && (
        <TcgdexLanguageSelect value={value} onChange={onChange} className="select w-full mt-2" />
      )}
    </div>
  )
}
