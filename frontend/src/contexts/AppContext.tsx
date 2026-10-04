import { createContext, useContext, useState, useCallback } from 'react'
import { api } from '../api'
import type { Entry, Category, Tag } from '../types'

interface AppState {
  entries: Entry[]
  categories: Category[]
  tags: Tag[]
  loading: boolean
  error: string | null
}

const AppContext = createContext<{
  state: AppState
  setEntries: (e: Entry[]) => void
  setCategories: (c: Category[]) => void
  setTags: (t: Tag[]) => void
  setLoading: (l: boolean) => void
  setError: (e: string | null) => void
  refreshAll: () => Promise<void>
} | null>(null)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AppState>({
    entries: [],
    categories: [],
    tags: [],
    loading: false,
    error: null,
  })

  const setEntries = (entries: Entry[]) => setState(s => ({ ...s, entries }))
  const setCategories = (categories: Category[]) => setState(s => ({ ...s, categories }))
  const setTags = (tags: Tag[]) => setState(s => ({ ...s, tags }))
  const setLoading = (loading: boolean) => setState(s => ({ ...s, loading }))
  const setError = (error: string | null) => setState(s => ({ ...s, error }))

  const refreshAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [entries, categories, tags] = await Promise.all([
        api.getEntries({ limit: 200 }),
        api.getCategories(),
        api.getTags(),
      ])
      setEntries(entries)
      setCategories(categories)
      setTags(tags)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  return (
    <AppContext.Provider value={{ state, setEntries, setCategories, setTags, setLoading, setError, refreshAll }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
