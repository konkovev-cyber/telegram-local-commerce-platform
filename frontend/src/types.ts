export interface Category {
  id: number
  name: string
  slug: string
  entry_count: number
}

export interface Tag {
  id: number
  name: string
}

export interface Attachment {
  id: number
  entry_id: number
  original_filename: string
  stored_filename: string
  mime_type: string
  size: number
  created_at: string
}

export interface Entry {
  id: number
  title: string
  content: string
  category_id: number | null
  category_name: string | null
  is_favorite: boolean
  tags: Tag[]
  attachments: Attachment[]
  created_at: string
  updated_at: string
}

export interface SearchResult {
  entries: Entry[]
  total: number
}

export interface ImportResult {
  created: number
  entries: Entry[]
}

export interface HistoryEntry {
  id: number
  entry_id: number
  title: string
  content: string
  created_at: string
}

export interface Employee {
  id: number
  full_name: string
  department: string | null
  position: string | null
  phone: string | null
  email: string | null
  sip: string | null
  domain_login: string | null
  room: string | null
  notes: string | null
  asset_count: number
}

export interface Asset {
  id: number
  asset_type: string
  vendor: string | null
  model: string | null
  serial_number: string | null
  inventory_number: string | null
  mac_address: string | null
  ip_address: string | null
  status: string
  location: string | null
  employee_id: number | null
  employee_name: string | null
  purchase_date: string | null
  notes: string | null
}

export interface InventoryMeta {
  types: string[]
  statuses: string[]
}
