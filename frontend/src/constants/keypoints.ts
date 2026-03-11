/** 25 个人体关键点名称（与后端 COCO 导出一致） */
export const KEYPOINT_NAMES = [
  'head_top',
  'head_center',
  'chin',
  'neck',
  'chest_center',
  'spine_mid',
  'pelvis_center',
  'left_shoulder',
  'left_elbow',
  'left_wrist',
  'left_palm',
  'right_shoulder',
  'right_elbow',
  'right_wrist',
  'right_palm',
  'left_hip',
  'left_knee',
  'left_ankle',
  'left_toe',
  'right_hip',
  'right_knee',
  'right_ankle',
  'right_toe',
  'racket_grip',
  'racket_head',
] as const

/** 骨架连线（关键点索引对） */
export const SKELETON_EDGES: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6],
  [3, 7], [7, 8], [8, 9], [9, 10],
  [3, 11], [11, 12], [12, 13], [13, 14],
  [6, 15], [15, 16], [16, 17], [17, 18],
  [6, 19], [19, 20], [20, 21], [21, 22],
  [13, 23], [23, 24],
]

/** 各关键点按部位分色（索引与 KEYPOINT_NAMES 一致） */
export const KEYPOINT_COLORS: string[] = [
  '#E74C3C', '#E74C3C', '#E74C3C',           // 头: 头顶/头中/下巴
  '#3498DB', '#3498DB', '#3498DB', '#3498DB', // 躯干: 颈/胸/脊柱中/骨盆
  '#2ECC71', '#2ECC71', '#2ECC71', '#2ECC71', // 左臂: 肩/肘/腕/掌
  '#9B59B6', '#9B59B6', '#9B59B6', '#9B59B6', // 右臂: 肩/肘/腕/掌
  '#F39C12', '#F39C12', '#F39C12', '#F39C12', // 左腿: 髋/膝/踝/脚尖
  '#1ABC9C', '#1ABC9C', '#1ABC9C', '#1ABC9C', // 右腿: 髋/膝/踝/脚尖
  '#E67E22', '#E67E22',                       // 球拍: 拍柄/拍头
]

/** 关键点中文标签 */
export const KEYPOINT_LABELS: Record<string, string> = {
  head_top: '头顶',
  head_center: '头中',
  chin: '下巴',
  neck: '颈部',
  chest_center: '胸中',
  spine_mid: '脊柱中',
  pelvis_center: '骨盆',
  left_shoulder: '左肩',
  left_elbow: '左肘',
  left_wrist: '左腕',
  left_palm: '左掌',
  right_shoulder: '右肩',
  right_elbow: '右肘',
  right_wrist: '右腕',
  right_palm: '右掌',
  left_hip: '左髋',
  left_knee: '左膝',
  left_ankle: '左踝',
  left_toe: '左脚尖',
  right_hip: '右髋',
  right_knee: '右膝',
  right_ankle: '右踝',
  right_toe: '右脚尖',
  racket_grip: '拍柄',
  racket_head: '拍头',
}

export interface KeypointItem {
  name: string
  x: number
  y: number
  visibility: number
}

export function createEmptyKeypoints(): KeypointItem[] {
  return KEYPOINT_NAMES.map((name) => ({ name, x: 0, y: 0, visibility: 0 }))
}

export function keypointsFromApi(data: unknown): KeypointItem[] {
  const base = createEmptyKeypoints()
  if (!Array.isArray(data)) return base
  for (const item of data) {
    if (item && typeof item === 'object' && 'name' in item) {
      const name = String((item as any).name)
      const idx = base.findIndex((b) => b.name === name)
      if (idx >= 0) {
        base[idx] = {
          name,
          x: Number((item as any).x) ?? 0,
          y: Number((item as any).y) ?? 0,
          visibility: Number((item as any).visibility) ?? 2,
        }
      }
    }
  }
  return base
}
