import * as XLSX from 'xlsx'
import { friendlyError } from '../api'

export const SN_PATTERN = /^[A-Z0-9]{16}$/

export function normalizeSns(text: string): string[] {
  return text
    .split(/[\r\n,，;；\t]+/)
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)
}

export function validateSns(values: string[]): { valid: string[]; invalid: string[] } {
  const valid: string[] = []
  const invalid: string[] = []
  values.forEach((v) => {
    if (SN_PATTERN.test(v)) valid.push(v)
    else invalid.push(v)
  })
  return { valid, invalid }
}

export function dedupe(values: string[]): string[] {
  return Array.from(new Set(values))
}

export async function parseSnFile(file: File): Promise<{ values: string[]; errorMessage?: string }> {
  const ext = (file.name.split('.').pop() || '').toLowerCase()
  if (!['xlsx', 'xls', 'csv', 'txt'].includes(ext)) {
    return { values: [], errorMessage: '仅支持 .xlsx / .xls / .csv / .txt 文件' }
  }
  if (file.size > 5 * 1024 * 1024) {
    return { values: [], errorMessage: '文件不能超过 5MB' }
  }
  try {
    const buffer = await file.arrayBuffer()
    const wb = XLSX.read(buffer, { type: 'array' })
    const ws = wb.Sheets[wb.SheetNames[0]]
    if (!ws) return { values: [], errorMessage: '文件中没有可读取的工作表' }
    const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' }) as unknown[][]
    const headers = (rows[0] || []).map(cell => String(cell ?? '').trim().toLowerCase())
    const snIndex = headers.findIndex(header => ['sn', 'sn号', 'sn码', 'serialno', 'serial number'].includes(header))
    const source = snIndex >= 0
      ? rows.slice(1).map(row => row[snIndex])
      : rows.flat()
    const values = source
      .map(cell => String(cell ?? '').trim().toUpperCase())
      .filter(v => v && v !== 'SN' && !v.startsWith('示例'))
    if (!values.length) return { values: [], errorMessage: '未从文件中读取到 SN 数据' }
    return { values: dedupe(values) }
  } catch (e: any) {
    return { values: [], errorMessage: friendlyError(e, '文件解析失败，请检查文件格式') }
  }
}

export async function parseDefectCodeFile(file: File): Promise<{ rows: Record<string, string>[]; errorMessage?: string }> {
  const ext = (file.name.split('.').pop() || '').toLowerCase()
  if (!['xlsx', 'xls', 'csv'].includes(ext)) {
    return { rows: [], errorMessage: '仅支持 .xlsx / .xls / .csv 文件' }
  }
  if (file.size > 5 * 1024 * 1024) return { rows: [], errorMessage: '文件不能超过 5MB' }
  try {
    const buffer = await file.arrayBuffer()
    const wb = XLSX.read(buffer, { type: 'array' })
    const ws = wb.Sheets[wb.SheetNames[0]]
    if (!ws) return { rows: [], errorMessage: '文件中没有可读取的工作表' }
    const rows = XLSX.utils.sheet_to_json(ws, { defval: '' }) as Record<string, any>[]
    const pick = (row: Record<string, any>, names: string[]) => {
      const hit = Object.keys(row).find(key => names.includes(String(key).trim()))
      return hit ? String(row[hit] ?? '').trim() : ''
    }
    const result = rows
      .map(row => ({
        productCode: pick(row, ['产品编码', 'productCode']),
        productName: pick(row, ['产品名称', 'productName']),
        stationCode: pick(row, ['工站编码', '工站', 'stationCode']),
        stationName: pick(row, ['工站名称', 'stationName']),
        repairMethod: pick(row, ['维修手段', 'repairMethod']),
        name: pick(row, ['不良名称', '名称', 'name']),
        description: pick(row, ['说明', 'description']),
      }))
      .filter(row => row.name && !row.name.startsWith('#') && !row.name.startsWith('例') && !row.name.startsWith('示例'))
    if (!result.length) return { rows: [], errorMessage: '未从文件中读取到不良代码数据' }
    return { rows: result }
  } catch (e: any) {
    return { rows: [], errorMessage: friendlyError(e, '文件解析失败，请检查格式') }
  }
}

export function downloadSnTemplate() {
  const rows = [
    ['SN'],
    ['DAP93226AS00019D'],
    ['DAP93226AS000294'],
  ]
  const ws = XLSX.utils.aoa_to_sheet(rows)
  ws['!cols'] = [{ wch: 24 }]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'SN清单')
  XLSX.writeFile(wb, 'SN导入模板.xlsx')
}
