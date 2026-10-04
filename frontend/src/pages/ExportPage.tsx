import { useState } from 'react'
import { api } from '../api'

export default function ExportPage() {
  const [exporting, setExporting] = useState<string | null>(null)
  const [importContent, setImportContent] = useState('')
  const [importResult, setImportResult] = useState<string | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const [separator, setSeparator] = useState('')

  const downloadFile = (content: string, filename: string, mime = 'text/plain') => {
    const blob = new Blob([content], { type: mime })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleExportJson = async () => {
    setExporting('json')
    try {
      const text = await api.exportJson()
      downloadFile(text, 'уголок-сисадмина-export.json', 'application/json')
    } catch (e: any) {
      alert(e.message)
    } finally {
      setExporting(null)
    }
  }

  const handleExportMd = async () => {
    setExporting('md')
    try {
      const data = await api.exportMarkdown()
      let allMd = '# Уголок сисадмина — Выгрузка\n\n'
      for (const [cat, entries] of Object.entries(data)) {
        allMd += `## ${cat}\n\n`
        for (const md of entries as string[]) {
          allMd += md + '\n---\n\n'
        }
      }
      downloadFile(allMd, 'уголок-сисадмина-export.md', 'text/markdown')
    } catch (e: any) {
      alert(e.message)
    } finally {
      setExporting(null)
    }
  }

  const handleImport = async () => {
    setImportResult(null)
    setImportError(null)
    if (!importContent.trim()) {
      setImportError('Вставьте текст для импорта')
      return
    }
    try {
      const res = await api.importTxt(importContent, undefined, separator || undefined)
      setImportResult(`Импортировано: ${res.created} записей`)
      setImportContent('')
    } catch (e: any) {
      setImportError(e.message || 'Ошибка импорта')
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        <h2 className="text-xl font-semibold text-gray-100">Экспорт и импорт</h2>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-gray-200 font-medium mb-4">Экспорт</h3>
          <div className="space-y-3">
            <button onClick={handleExportJson} disabled={exporting === 'json'}
              className="w-full bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-gray-200 px-4 py-3 rounded-lg text-sm text-left flex items-center justify-between">
              <span>Экспорт в JSON</span>
              {exporting === 'json' && <span className="text-gray-500">...</span>}
            </button>
            <button onClick={handleExportMd} disabled={exporting === 'md'}
              className="w-full bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-gray-200 px-4 py-3 rounded-lg text-sm text-left flex items-center justify-between">
              <span>Экспорт в Markdown</span>
              {exporting === 'md' && <span className="text-gray-500">...</span>}
            </button>
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-gray-200 font-medium mb-4">Импорт из TXT</h3>
          <p className="text-gray-500 text-sm mb-3">
            Вставьте текстовый файл ниже. Каждый раздел станет отдельной записью.
            Опционально: укажите разделитель (например <code className="text-yellow-400 bg-gray-800 px-1 rounded">===</code>) для разделения на несколько записей.
          </p>
          <textarea
            value={importContent}
            onChange={e => setImportContent(e.target.value)}
            placeholder="Вставьте текст сюда..."
            className="w-full h-48 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-200 outline-none focus:border-blue-500 font-mono resize-none"
          />
          <div className="flex items-center gap-3 mt-3">
            <input type="text" value={separator} onChange={e => setSeparator(e.target.value)}
              placeholder="Разделитель (необязательно, напр. ===)"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 outline-none" />
            <button onClick={handleImport}
              className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap">
              Импортировать
            </button>
          </div>
          {importResult && <p className="text-green-400 text-sm mt-2">{importResult}</p>}
          {importError && <p className="text-red-400 text-sm mt-2">{importError}</p>}
        </div>
      </div>
    </div>
  )
}
