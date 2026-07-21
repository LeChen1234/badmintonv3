/** Contact-centric annotation constants (monocular face-parameter chart). */

export const FACE_CORNER_NAMES = [
  'face_top',
  'face_bottom',
  'face_left',
  'face_right',
] as const

export const FACE_CORNER_LABELS: Record<string, string> = {
  face_top: '拍面上沿',
  face_bottom: '拍面下沿',
  face_left: '拍面左缘',
  face_right: '拍面右缘',
}

export const CONTACT_ZONES = [
  { value: 'sweet', label: '甜区' },
  { value: 'top', label: '拍头远端' },
  { value: 'bottom', label: '近柄侧' },
  { value: 'head_side', label: '拍面侧缘' },
  { value: 'throat', label: '拍颈附近' },
  { value: 'unknown', label: '未知/不可见' },
] as const

export const FACE_ATTITUDES = [
  { value: 'open', label: '开放拍面' },
  { value: 'square', label: '正面/中性' },
  { value: 'closed', label: '关闭拍面' },
  { value: 'unknown', label: '未知' },
] as const

export const SUPPORT_FEET = [
  { value: 'left', label: '左脚支撑' },
  { value: 'right', label: '右脚支撑' },
  { value: 'both', label: '双脚' },
  { value: 'unknown', label: '未知' },
] as const

export const ERROR_ATTRIBUTES = [
  { value: 'off_center_contact', label: '击球点偏离甜区' },
  { value: 'open_face', label: '拍面过于开放' },
  { value: 'closed_face', label: '拍面过于关闭' },
  { value: 'late_timing', label: '击球偏晚' },
  { value: 'early_timing', label: '击球偏早' },
  { value: 'unstable_base', label: '支撑不稳' },
  { value: 'poor_grip', label: '握拍问题' },
  { value: 'other', label: '其他' },
] as const

export const CONTACT_QUALITY_OPTIONS = [
  { value: 'standard', label: '标准' },
  { value: 'acceptable', label: '可接受' },
  { value: 'needs_correction', label: '需纠正' },
] as const

export interface ContactPoint {
  x: number | null
  y: number | null
  visibility: number
}

export interface ContactPayload {
  tolerance_flag: boolean
  shuttle: ContactPoint
  face_corners: { name: string; x: number; y: number; visibility: number }[]
  contact_point: ContactPoint
  contact_uv: { u: number | null; v: number | null }
  contact_zone: string | null
  face_attitude: string | null
  support_foot: string | null
  error_attributes: string[]
}

export function emptyContactPayload(): ContactPayload {
  return {
    tolerance_flag: false,
    shuttle: { x: null, y: null, visibility: 0 },
    face_corners: FACE_CORNER_NAMES.map((name) => ({
      name,
      x: 0,
      y: 0,
      visibility: 0,
    })),
    contact_point: { x: null, y: null, visibility: 0 },
    contact_uv: { u: null, v: null },
    contact_zone: null,
    face_attitude: null,
    support_foot: null,
    error_attributes: [],
  }
}

export function normalizeContactPayload(raw: unknown): ContactPayload {
  const base = emptyContactPayload()
  if (!raw || typeof raw !== 'object') return base
  const c = raw as Partial<ContactPayload>
  base.tolerance_flag = !!c.tolerance_flag
  if (c.shuttle) {
    base.shuttle = {
      x: typeof c.shuttle.x === 'number' ? c.shuttle.x : null,
      y: typeof c.shuttle.y === 'number' ? c.shuttle.y : null,
      visibility: c.shuttle.visibility ?? 0,
    }
  }
  if (Array.isArray(c.face_corners)) {
    base.face_corners = FACE_CORNER_NAMES.map((name) => {
      const found = c.face_corners!.find((f) => f.name === name)
      return found
        ? {
            name,
            x: Number(found.x) || 0,
            y: Number(found.y) || 0,
            visibility: found.visibility ?? 0,
          }
        : { name, x: 0, y: 0, visibility: 0 }
    })
  }
  if (c.contact_point) {
    base.contact_point = {
      x: typeof c.contact_point.x === 'number' ? c.contact_point.x : null,
      y: typeof c.contact_point.y === 'number' ? c.contact_point.y : null,
      visibility: c.contact_point.visibility ?? 0,
    }
  }
  if (c.contact_uv) {
    base.contact_uv = {
      u: typeof c.contact_uv.u === 'number' ? c.contact_uv.u : null,
      v: typeof c.contact_uv.v === 'number' ? c.contact_uv.v : null,
    }
  }
  base.contact_zone = c.contact_zone ?? null
  base.face_attitude = c.face_attitude ?? null
  base.support_foot = c.support_foot ?? null
  base.error_attributes = Array.isArray(c.error_attributes) ? [...c.error_attributes] : []
  return base
}

/** Inverse bilinear map from image % point into face chart [0,1]^2. */
export function bilinearUv(
  faceCorners: ContactPayload['face_corners'],
  px: number,
  py: number,
): { u: number; v: number } | null {
  const byName: Record<string, { x: number; y: number }> = {}
  for (const c of faceCorners) {
    if (c.visibility > 0) byName[c.name] = { x: c.x, y: c.y }
  }
  const need = ['face_top', 'face_bottom', 'face_left', 'face_right']
  if (!need.every((n) => byName[n])) return null

  const top = byName.face_top
  const bottom = byName.face_bottom
  const left = byName.face_left
  const right = byName.face_right
  const tl: [number, number] = [(top.x + left.x) / 2, (top.y + left.y) / 2]
  const tr: [number, number] = [(top.x + right.x) / 2, (top.y + right.y) / 2]
  const bl: [number, number] = [(bottom.x + left.x) / 2, (bottom.y + left.y) / 2]
  const br: [number, number] = [(bottom.x + right.x) / 2, (bottom.y + right.y) / 2]

  let u = 0.5
  let v = 0.5
  for (let i = 0; i < 8; i++) {
    const x =
      (1 - u) * (1 - v) * tl[0] +
      u * (1 - v) * tr[0] +
      (1 - u) * v * bl[0] +
      u * v * br[0]
    const y =
      (1 - u) * (1 - v) * tl[1] +
      u * (1 - v) * tr[1] +
      (1 - u) * v * bl[1] +
      u * v * br[1]
    const dxdu = (1 - v) * (tr[0] - tl[0]) + v * (br[0] - bl[0])
    const dxdv = (1 - u) * (bl[0] - tl[0]) + u * (br[0] - tr[0])
    const dydu = (1 - v) * (tr[1] - tl[1]) + v * (br[1] - bl[1])
    const dydv = (1 - u) * (bl[1] - tl[1]) + u * (br[1] - tr[1])
    const det = dxdu * dydv - dxdv * dydu
    if (Math.abs(det) < 1e-8) break
    const rx = x - px
    const ry = y - py
    u -= (dydv * rx - dxdv * ry) / det
    v -= (-dydu * rx + dxdu * ry) / det
    u = Math.max(0, Math.min(1, u))
    v = Math.max(0, Math.min(1, v))
  }
  return { u: Number(u.toFixed(4)), v: Number(v.toFixed(4)) }
}

export function recomputeContactUv(contact: ContactPayload): void {
  const cp = contact.contact_point
  if (cp.visibility <= 0 || cp.x == null || cp.y == null) {
    contact.contact_uv = { u: null, v: null }
    return
  }
  const uv = bilinearUv(contact.face_corners, cp.x, cp.y)
  contact.contact_uv = uv ? { u: uv.u, v: uv.v } : { u: null, v: null }
}
