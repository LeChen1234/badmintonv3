<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button @click="$router.push('/tasks')" type="info" plain size="small">
              返回任务列表
            </el-button>
            <span style="margin-left: 12px; font-weight: 600;">
              标注 - {{ batchName }} (帧 {{ currentFrame }}/{{ totalFrames }})
            </span>
          </div>
          <div class="header-right">
            <el-tag v-if="currentAnnotation?.annotator_name" type="info" style="margin-right: 8px;">
              标注人: {{ currentAnnotation.annotator_name }}
            </el-tag>
            <el-tag :type="statusTagType">{{ statusLabel }}</el-tag>
          </div>
        </div>
      </template>

      <!-- 无帧时：上传图片或视频 -->
      <div v-if="totalFrames === 0" class="upload-section">
        <el-upload
          ref="uploadRef"
          class="upload-area"
          drag
          :auto-upload="false"
          :limit="200"
          :on-change="onFileChange"
          :on-exceed="() => ElMessage.warning('最多 200 张图片')"
          accept=".jpg,.jpeg,.png,.bmp,.gif,.webp,.mp4,.avi,.mov,.mkv,.webm"
          multiple
        >
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-text">
            <p>将图片或视频拖到此处，或点击上传</p>
            <p class="upload-hint">支持多张图片 (jpg/png/gif等) 或一个视频 (mp4/avi/mov等)，视频将自动按帧提取</p>
          </div>
        </el-upload>
        <div class="upload-actions">
          <el-button type="primary" :loading="uploading" @click="submitUpload" :disabled="!pendingFiles.length">
            开始上传 ({{ pendingFiles.length }} 个文件)
          </el-button>
        </div>
      </div>

      <template v-else>
        <el-row :gutter="20">
          <el-col :span="16">
            <div class="frame-area">
              <!-- 帧图片 + 关键点画布 + 标注可视化叠加 -->
              <div class="frame-wrapper" v-if="frameImageUrl">
                <div class="frame-img-wrap" ref="frameWrapRef">
                  <img
                    ref="frameImgRef"
                    :src="frameImageUrl"
                    class="frame-img"
                    alt="当前帧"
                    @error="onImageError"
                    @load="drawKeypointsCanvas"
                  />
                  <canvas
                    ref="canvasRef"
                    class="keypoints-canvas"
                    @click="onCanvasClick"
                    @mousedown="onCanvasMouseDown"
                    @mousemove="onCanvasMouseMove"
                    @mouseup="onCanvasMouseUp"
                    @mouseleave="onCanvasMouseUp"
                  />
                </div>
                <div class="annotation-overlay" v-if="currentAnnotation || form.action_type || form.action_phase || form.quality_rating">
                  <div class="overlay-tags">
                    <el-tag v-if="form.action_type" type="primary" size="small">{{ actionTypeLabel(form.action_type) }}</el-tag>
                    <el-tag v-if="form.action_phase" type="success" size="small">{{ actionPhaseLabel(form.action_phase) }}</el-tag>
                    <el-tag v-if="form.quality_rating" type="warning" size="small">{{ qualityLabel(form.quality_rating) }}</el-tag>
                  </div>
                  <div class="overlay-annotator" v-if="currentAnnotation?.annotator_name">
                    标注: {{ currentAnnotation.annotator_name }} · {{ statusLabel }}
                  </div>
                </div>
              </div>
              <div class="frame-placeholder" v-else>
                <el-icon :size="48"><Picture /></el-icon>
                <p>帧 #{{ currentFrame }}</p>
                <p class="frame-hint" v-if="loadingImage">加载中...</p>
                <p class="frame-hint" v-else>无图像</p>
              </div>
            </div>

            <div class="frame-nav">
              <el-button :disabled="currentFrame <= 1" @click="prevFrame">上一帧</el-button>
              <el-input-number
                v-model="currentFrame"
                :min="1"
                :max="totalFrames"
                size="small"
                style="width: 120px; margin: 0 12px;"
                @change="loadAnnotation"
              />
              <el-button :disabled="currentFrame >= totalFrames" @click="nextFrame">下一帧</el-button>
              <span style="margin-left: 16px; color: #909399; font-size: 13px;">
                已标注 {{ annotatedCount }}/{{ totalFrames }} 帧
              </span>
            </div>

            <div class="re-upload-row">
              <el-button size="small" type="info" plain @click="showReUpload = true">重新上传图片/视频</el-button>
            </div>
          </el-col>

          <el-col :span="8">
            <el-form label-width="90px" label-position="top" class="annotation-form">
              <el-form-item label="动作类型">
                <el-select v-model="form.action_type" placeholder="选择动作类型" clearable style="width: 100%;">
                  <el-option label="杀球 (Smash)" value="smash" />
                  <el-option label="高远球 (Clear)" value="clear" />
                  <el-option label="吊球 (Drop Shot)" value="drop_shot" />
                  <el-option label="搓球 (Net Shot)" value="net_shot" />
                  <el-option label="挑球 (Lift)" value="lift" />
                  <el-option label="推球 (Push)" value="push" />
                  <el-option label="扑球 (Rush)" value="rush" />
                  <el-option label="抽球 (Drive)" value="drive" />
                  <el-option label="发球 (Serve)" value="serve" />
                  <el-option label="接发球 (Receive)" value="receive" />
                  <el-option label="其他 (Other)" value="other" />
                </el-select>
              </el-form-item>

              <el-form-item label="动作阶段">
                <el-select v-model="form.action_phase" placeholder="选择阶段" clearable style="width: 100%;">
                  <el-option label="准备 (Preparation)" value="preparation" />
                  <el-option label="引拍 (Backswing)" value="backswing" />
                  <el-option label="击球 (Impact)" value="impact" />
                  <el-option label="随挥 (Follow-through)" value="follow_through" />
                  <el-option label="回位 (Recovery)" value="recovery" />
                </el-select>
              </el-form-item>

              <el-form-item label="动作质量">
                <el-select v-model="form.quality_rating" placeholder="评分" clearable style="width: 100%;">
                  <el-option label="优秀" value="excellent" />
                  <el-option label="良好" value="good" />
                  <el-option label="一般" value="average" />
                  <el-option label="较差" value="poor" />
                </el-select>
              </el-form-item>

              <el-form-item label="备注">
                <el-input v-model="form.notes" type="textarea" :rows="3" placeholder="可选备注" />
              </el-form-item>

              <el-divider />
              <el-form-item label="关键点标注（25 点）">
                <div class="keypoint-hint">点击下方按钮选择节点，再在左侧画面点击设点或拖拽已有点调整；不同部位颜色不同。</div>
                <div class="keypoint-buttons">
                  <el-button
                    v-for="(kp, idx) in keypointsList"
                    :key="kp.name"
                    size="small"
                    :type="selectedKeypointIndex === idx ? 'primary' : undefined"
                    :class="{ 'keypoint-btn-set': kp.visibility > 0 }"
                    @click="selectedKeypointIndex = idx"
                  >
                    <span class="keypoint-btn-dot" :style="{ background: KEYPOINT_COLORS[idx] }" />
                    {{ KEYPOINT_LABELS[kp.name] || kp.name }}
                  </el-button>
                </div>
                <div class="keypoint-actions">
                  <el-button size="small" type="primary" :loading="predictingKeypoints" @click="applyPredictKeypoints">
                    算法辅助标注（多人识别）
                  </el-button>
                  <el-button size="small" @click="clearCurrentKeypoint">清除当前点</el-button>
                  <el-button size="small" @click="clearAllKeypoints">清除全部</el-button>
                </div>
              </el-form-item>

              <el-divider />

              <div class="action-buttons">
                <el-button type="primary" @click="saveAnnotation" :loading="saving">
                  {{ currentAnnotation ? '更新标注' : '保存标注' }}
                </el-button>
                <el-button type="success" @click="saveAndNext" :loading="saving">
                  保存并下一帧
                </el-button>
              </div>

              <el-divider />

              <div class="batch-actions">
                <el-button type="warning" @click="submitAll" :loading="submitting" style="width: 100%; margin-bottom: 8px;">
                  提交所有草稿
                </el-button>
                <el-button v-if="canConfirm" type="success" @click="confirmAll" :loading="confirming" style="width: 100%;">
                  确认所有已提交标注
                </el-button>
              </div>
            </el-form>
          </el-col>
        </el-row>
      </template>
    </el-card>

    <el-dialog v-model="showReUpload" title="重新上传" width="500px">
      <p>重新上传将替换当前任务下的所有帧，已有标注会保留帧序号对应关系。</p>
      <template #footer>
        <el-button @click="showReUpload = false">取消</el-button>
        <el-button type="primary" @click="goReUpload">去上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPersonSelect" title="选择要应用的人" width="400px">
      <p>检测到 {{ predictedPersons.length }} 人，请选择要应用到当前帧骨架的一人：</p>
      <div class="person-select-btns">
        <el-button
          v-for="(_, idx) in predictedPersons"
          :key="idx"
          type="primary"
          plain
          @click="applyPredictedPerson(idx)"
        >
          第 {{ idx + 1 }} 人
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { annotationApi, taskApi } from '@/api'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { Picture, UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadFiles, UploadInstance } from 'element-plus'
import {
  KEYPOINT_NAMES,
  SKELETON_EDGES,
  KEYPOINT_LABELS,
  KEYPOINT_COLORS,
  createEmptyKeypoints,
  keypointsFromApi,
  type KeypointItem,
} from '@/constants/keypoints'

const route = useRoute()
const authStore = useAuthStore()
const batchId = Number(route.params.batchId)

const batchName = ref('')
const totalFrames = ref(0)
const currentFrame = ref(1)
const annotatedCount = ref(0)
const currentAnnotation = ref<any>(null)
const saving = ref(false)
const submitting = ref(false)
const confirming = ref(false)
const uploading = ref(false)
const loadingImage = ref(false)
const showReUpload = ref(false)

const frameImageUrl = ref<string | null>(null)
const pendingFiles = ref<UploadFile[]>([])
const uploadRef = ref<UploadInstance>()

const form = reactive({
  action_type: '',
  action_phase: '',
  quality_rating: '',
  notes: '',
})

const keypointsList = ref<KeypointItem[]>(createEmptyKeypoints())
const selectedKeypointIndex = ref(0)
const frameImgRef = ref<HTMLImageElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const frameWrapRef = ref<HTMLDivElement | null>(null)
const draggingPointIndex = ref<number | null>(null)
const predictingKeypoints = ref(false)
/** 本次按下后是否发生了拖拽，用于区分点击与拖拽 */
const didDragThisPointer = ref(false)
/** 算法检测到的多人关键点，用于弹窗选择 */
const predictedPersons = ref<{ keypoints: { name: string; x: number; y: number; visibility: number }[] }[]>([])
const showPersonSelect = ref(false)

const actionTypeLabel = (v: string) =>
  ({ smash: '杀球', clear: '高远球', drop_shot: '吊球', net_shot: '搓球', lift: '挑球', push: '推球', rush: '扑球', drive: '抽球', serve: '发球', receive: '接发球', other: '其他' }[v] || v)
const actionPhaseLabel = (v: string) =>
  ({ preparation: '准备', backswing: '引拍', impact: '击球', follow_through: '随挥', recovery: '回位' }[v] || v)
const qualityLabel = (v: string) =>
  ({ excellent: '优秀', good: '良好', average: '一般', poor: '较差' }[v] || v)

const canConfirm = computed(() => {
  const role = authStore.user?.role
  return role === 'admin' || role === 'expert' || role === 'leader'
})

const statusLabels: Record<string, string> = { draft: '草稿', submitted: '已提交', confirmed: '已确认', rejected: '已退回' }
const statusTagTypes: Record<string, string> = { draft: '', submitted: 'warning', confirmed: 'success', rejected: 'danger' }

const statusLabel = computed(() => {
  if (!currentAnnotation.value) return '未标注'
  const s = currentAnnotation.value.status as string
  return statusLabels[s] ?? s
})

const statusTagType = computed(() => {
  if (!currentAnnotation.value) return 'info'
  const s = currentAnnotation.value.status as string
  return statusTagTypes[s] ?? 'info'
})

async function loadBatchInfo() {
  try {
    const res = await taskApi.get(batchId)
    batchName.value = res.data.name
    const framesRes = await taskApi.getFrames(batchId)
    const frames = (framesRes.data || []) as { frame_index: number; file_path: string }[]
    if (frames.length === 0) {
      totalFrames.value = 0
    } else {
      totalFrames.value = res.data.total_frames ?? frames.length
    }
  } catch { /* handled */ }
}

function revokeFrameImageUrl() {
  if (frameImageUrl.value) {
    URL.revokeObjectURL(frameImageUrl.value)
    frameImageUrl.value = null
  }
}

async function loadFrameImage() {
  if (totalFrames.value < 1 || currentFrame.value < 1) return
  revokeFrameImageUrl()
  loadingImage.value = true
  try {
    const url = taskApi.getFrameImageUrl(batchId, currentFrame.value)
    const res = await request.get(url, { responseType: 'blob' })
    frameImageUrl.value = URL.createObjectURL(res.data)
  } catch {
    frameImageUrl.value = null
  } finally {
    loadingImage.value = false
  }
}

function onImageError() {
  revokeFrameImageUrl()
}

async function loadAnnotation() {
  try {
    const res = await annotationApi.list(batchId, { frame_index: currentFrame.value })
    if (res.data && res.data.length > 0) {
      currentAnnotation.value = res.data[0]
      form.action_type = res.data[0].action_type || ''
      form.action_phase = res.data[0].action_phase || ''
      form.quality_rating = res.data[0].quality_rating || ''
      form.notes = res.data[0].notes || ''
      keypointsList.value = keypointsFromApi(res.data[0].keypoints)
    } else {
      currentAnnotation.value = null
      form.action_type = ''
      form.action_phase = ''
      form.quality_rating = ''
      form.notes = ''
      keypointsList.value = createEmptyKeypoints()
    }
  } catch { /* handled */ }
  await loadFrameImage()
}

async function loadAnnotatedCount() {
  try {
    const res = await annotationApi.list(batchId, { limit: 2000 })
    const frames = new Set((res.data || []).map((a: any) => a.frame_index))
    annotatedCount.value = frames.size
  } catch { /* handled */ }
}

function getKeypointsPayload() {
  return keypointsList.value.filter((kp) => kp.visibility > 0).map((kp) => ({ name: kp.name, x: kp.x, y: kp.y, visibility: kp.visibility }))
}

async function saveAnnotation() {
  saving.value = true
  try {
    const kpPayload = getKeypointsPayload()
    if (currentAnnotation.value) {
      await annotationApi.update(currentAnnotation.value.id, {
        keypoints: kpPayload.length ? kpPayload : null,
        action_type: form.action_type || null,
        action_phase: form.action_phase || null,
        quality_rating: form.quality_rating || null,
        notes: form.notes || null,
      })
      ElMessage.success('标注已更新')
    } else {
      await annotationApi.create({
        task_batch_id: batchId,
        frame_index: currentFrame.value,
        keypoints: kpPayload.length ? kpPayload : null,
        action_type: form.action_type || null,
        action_phase: form.action_phase || null,
        quality_rating: form.quality_rating || null,
        notes: form.notes || null,
      })
      ElMessage.success('标注已保存')
    }
    await loadAnnotation()
    await loadAnnotatedCount()
  } catch { /* handled */ }
  finally { saving.value = false }
}

async function saveAndNext() {
  await saveAnnotation()
  if (currentFrame.value < totalFrames.value) {
    currentFrame.value++
    await loadAnnotation()
  }
}

function prevFrame() {
  if (currentFrame.value > 1) {
    currentFrame.value--
    loadAnnotation()
  }
}

function nextFrame() {
  if (currentFrame.value < totalFrames.value) {
    currentFrame.value++
    loadAnnotation()
  }
}

async function submitAll() {
  submitting.value = true
  try {
    await annotationApi.submit(batchId)
    ElMessage.success('所有草稿已提交')
    await loadAnnotation()
  } catch { /* handled */ }
  finally { submitting.value = false }
}

async function confirmAll() {
  confirming.value = true
  try {
    await annotationApi.confirm({ task_batch_id: batchId })
    ElMessage.success('所有已提交标注已确认')
    await loadAnnotation()
  } catch { /* handled */ }
  finally { confirming.value = false }
}

function onFileChange(_file: UploadFile, fileList: UploadFiles) {
  pendingFiles.value = fileList
}

async function submitUpload() {
  if (!pendingFiles.value.length) return
  const formData = new FormData()
  const isVideo = pendingFiles.value.length === 1 && /\.(mp4|avi|mov|mkv|webm|flv)$/i.test(pendingFiles.value[0].name || '')
  if (isVideo) {
    const file = pendingFiles.value[0].raw
    if (file) formData.append('file', file)
  } else {
    pendingFiles.value.forEach((f) => {
      if (f.raw) formData.append('files', f.raw)
    })
  }
  uploading.value = true
  try {
    await taskApi.upload(batchId, formData)
    ElMessage.success('上传成功')
    pendingFiles.value = []
    uploadRef.value?.clearFiles()
    await loadBatchInfo()
    await loadAnnotation()
    await loadAnnotatedCount()
  } catch { /* handled */ }
  finally { uploading.value = false }
}

function goReUpload() {
  showReUpload.value = false
  totalFrames.value = 0
  revokeFrameImageUrl()
  loadBatchInfo()
}

function drawKeypointsCanvas() {
  nextTick(() => {
    const canvas = canvasRef.value
    const img = frameImgRef.value
    if (!canvas || !img || !img.complete) return
    const w = img.offsetWidth
    const h = img.offsetHeight
    if (w <= 0 || h <= 0) return
    canvas.width = w
    canvas.height = h
    canvas.style.width = w + 'px'
    canvas.style.height = h + 'px'
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, w, h)
    const kps = keypointsList.value
    ctx.strokeStyle = 'rgba(0, 200, 100, 0.8)'
    ctx.lineWidth = 2
    for (const [i, j] of SKELETON_EDGES) {
      if (i >= kps.length || j >= kps.length) continue
      const a = kps[i]
      const b = kps[j]
      if (a.visibility > 0 && b.visibility > 0) {
        const x1 = (a.x / 100) * w
        const y1 = (a.y / 100) * h
        const x2 = (b.x / 100) * w
        const y2 = (b.y / 100) * h
        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.stroke()
      }
    }
    for (let i = 0; i < kps.length; i++) {
      const kp = kps[i]
      if (kp.visibility <= 0) continue
      const x = (kp.x / 100) * w
      const y = (kp.y / 100) * h
      const color = KEYPOINT_COLORS[i] || '#409eff'
      ctx.fillStyle = color
      ctx.strokeStyle = i === selectedKeypointIndex.value ? '#ff0' : '#fff'
      ctx.lineWidth = i === selectedKeypointIndex.value ? 2 : 1
      ctx.beginPath()
      ctx.arc(x, y, 6, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    }
  })
}

function onCanvasClick(e: MouseEvent) {
  if (didDragThisPointer.value) {
    didDragThisPointer.value = false
    return
  }
  const canvas = canvasRef.value
  if (!canvas) return
  const hit = hitTestKeypoint(canvas, e.clientX, e.clientY)
  if (hit >= 0) {
    selectedKeypointIndex.value = hit
    return
  }
  const rect = canvas.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  const idx = selectedKeypointIndex.value
  if (idx >= 0 && idx < keypointsList.value.length) {
    keypointsList.value[idx] = {
      ...keypointsList.value[idx],
      x: Math.max(0, Math.min(100, x)),
      y: Math.max(0, Math.min(100, y)),
      visibility: 2,
    }
    keypointsList.value = [...keypointsList.value]
    drawKeypointsCanvas()
  }
}

/** 命中半径（百分比），便于在图上点选/拖拽节点 */
const HIT_RADIUS_PCT = 6

function hitTestKeypoint(canvas: HTMLCanvasElement, clientX: number, clientY: number): number {
  const rect = canvas.getBoundingClientRect()
  const px = ((clientX - rect.left) / rect.width) * 100
  const py = ((clientY - rect.top) / rect.height) * 100
  const kps = keypointsList.value
  for (let i = kps.length - 1; i >= 0; i--) {
    if (kps[i].visibility <= 0) continue
    if (Math.hypot(kps[i].x - px, kps[i].y - py) < HIT_RADIUS_PCT) return i
  }
  return -1
}

function onCanvasMouseDown(e: MouseEvent) {
  const canvas = canvasRef.value
  if (!canvas) return
  didDragThisPointer.value = false
  const rect = canvas.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  let idx = hitTestKeypoint(canvas, e.clientX, e.clientY)
  if (idx >= 0) {
    draggingPointIndex.value = idx
    selectedKeypointIndex.value = idx
  } else {
    idx = selectedKeypointIndex.value
    if (idx >= 0 && idx < keypointsList.value.length) {
      draggingPointIndex.value = idx
      keypointsList.value[idx] = {
        ...keypointsList.value[idx],
        x: Math.max(0, Math.min(100, x)),
        y: Math.max(0, Math.min(100, y)),
        visibility: 2,
      }
      keypointsList.value = [...keypointsList.value]
      drawKeypointsCanvas()
    }
  }
}

function onCanvasMouseMove(e: MouseEvent) {
  if (draggingPointIndex.value === null) return
  didDragThisPointer.value = true
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  const idx = draggingPointIndex.value
  keypointsList.value[idx] = {
    ...keypointsList.value[idx],
    x: Math.max(0, Math.min(100, x)),
    y: Math.max(0, Math.min(100, y)),
  }
  keypointsList.value = [...keypointsList.value]
  drawKeypointsCanvas()
}

function onCanvasMouseUp() {
  draggingPointIndex.value = null
}

function clearCurrentKeypoint() {
  const idx = selectedKeypointIndex.value
  if (idx >= 0 && idx < keypointsList.value.length) {
    keypointsList.value[idx] = { ...keypointsList.value[idx], x: 0, y: 0, visibility: 0 }
    keypointsList.value = [...keypointsList.value]
    drawKeypointsCanvas()
  }
}

function clearAllKeypoints() {
  keypointsList.value = createEmptyKeypoints()
  drawKeypointsCanvas()
}

async function applyPredictKeypoints() {
  if (totalFrames.value < 1 || currentFrame.value < 1) return
  predictingKeypoints.value = true
  predictedPersons.value = []
  showPersonSelect.value = false
  try {
    const res = await taskApi.predictKeypoints(batchId, currentFrame.value)
    const persons = res.data?.persons
    if (!Array.isArray(persons) || persons.length === 0) {
      ElMessage.warning('未检测到人体关键点，请确认画面中有人体')
      return
    }
    if (persons.length === 1) {
      keypointsList.value = keypointsFromApi(persons[0].keypoints)
      drawKeypointsCanvas()
      ElMessage.success('已应用算法骨架，可继续微调或补标球拍等点位')
      return
    }
    predictedPersons.value = persons
    showPersonSelect.value = true
  } catch {
    // 错误已由 request 拦截器提示
  } finally {
    predictingKeypoints.value = false
  }
}

function applyPredictedPerson(personIndex: number) {
  const persons = predictedPersons.value
  if (personIndex >= 0 && personIndex < persons.length) {
    keypointsList.value = keypointsFromApi(persons[personIndex].keypoints)
    drawKeypointsCanvas()
    ElMessage.success('已应用第 ' + (personIndex + 1) + ' 人骨架，可继续微调或补标球拍')
  }
  showPersonSelect.value = false
  predictedPersons.value = []
}

function onKeydown(e: KeyboardEvent) {
  if (totalFrames.value < 1) return
  const target = e.target as HTMLElement
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || (target as HTMLInputElement).isContentEditable) return
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    prevFrame()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    nextFrame()
  } else if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    saveAnnotation()
  }
}

watch(currentFrame, () => loadAnnotation())
watch(keypointsList, () => drawKeypointsCanvas(), { deep: true })
onMounted(async () => {
  await loadBatchInfo()
  if (totalFrames.value > 0) {
    await loadAnnotation()
    await loadAnnotatedCount()
  }
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  revokeFrameImageUrl()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-left, .header-right {
  display: flex;
  align-items: center;
}

.upload-section {
  padding: 24px 0;
}
.upload-area {
  width: 100%;
}
.upload-area :deep(.el-upload-dragger) {
  width: 100%;
  padding: 48px;
}
.upload-icon {
  font-size: 64px;
  color: var(--el-color-primary);
}
.upload-text {
  margin-top: 16px;
  color: #606266;
}
.upload-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}
.upload-actions {
  margin-top: 16px;
}

.frame-area {
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
  margin-bottom: 16px;
  position: relative;
}
.frame-wrapper {
  position: relative;
  width: 100%;
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.frame-img-wrap {
  position: relative;
  display: inline-block;
}
.frame-img {
  display: block;
  max-width: 100%;
  max-height: 500px;
  object-fit: contain;
  vertical-align: top;
}
.keypoints-canvas {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: auto;
  cursor: crosshair;
}
.keypoint-hint {
  font-size: 12px;
  color: #909399;
  margin-bottom: 10px;
  line-height: 1.4;
}
.keypoint-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.keypoint-buttons .el-button {
  margin: 0;
}
.keypoint-btn-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.keypoint-btn-set {
  font-weight: 600;
}
.annotation-overlay {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 12px;
}
.overlay-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.overlay-annotator {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.95);
  background: rgba(0, 0, 0, 0.5);
  padding: 4px 8px;
  border-radius: 4px;
  align-self: flex-start;
}
.frame-placeholder {
  text-align: center;
  color: #909399;
}
.frame-placeholder p {
  margin: 8px 0 0;
  font-size: 16px;
}
.frame-hint {
  font-size: 12px !important;
  color: #c0c4cc;
}
.frame-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}
.re-upload-row {
  margin-bottom: 16px;
}
.annotation-form {
  padding: 0 8px;
}
.action-buttons {
  display: flex;
  gap: 8px;
}
.batch-actions {
  margin-top: 8px;
}
.person-select-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
</style>
