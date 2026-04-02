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

      <el-alert
        v-if="mediaProcessStatus !== 'idle'"
        :title="mediaProcessTitle"
        :description="mediaProcessMessage || undefined"
        :type="mediaProcessAlertType"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      />

      <div v-if="chunkUploadActive" class="chunk-upload-progress">
        <div class="chunk-upload-head">
          <span class="chunk-upload-title">视频上传进度</span>
          <span class="chunk-upload-meta">
            {{ chunkUploadedCount }}/{{ chunkTotalCount }} 分块
            <span v-if="chunkUploadETA" class="chunk-eta">{{ chunkUploadETA }}</span>
          </span>
        </div>
        <el-progress :percentage="chunkUploadPercent" :stroke-width="12" />
      </div>

      <!-- 无帧时：上传图片或视频 -->
      <div v-if="totalFrames === 0" class="upload-section">
        <el-upload
          ref="uploadRef"
          class="upload-area"
          drag
          :disabled="isMediaProcessing"
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

        <div v-if="isVideoSelected" class="yolo-settings-card">
          <div class="yolo-settings-head">
            <span class="yolo-settings-title">视频预处理设置</span>
            <el-switch v-model="useYoloFilter" active-text="启用 YOLO 动作过滤" inactive-text="仅均匀抽帧" />
          </div>
          <p class="yolo-settings-desc">建议只在视频上传时开启。系统会先计算本视频的帧间欧氏距离分布，再按你选择的百分位自动筛帧。</p>

          <div v-if="useYoloFilter" class="threshold-controls">
            <span class="threshold-label">动作百分位 (P)</span>
            <el-input-number
              v-model="motionPercentile"
              :min="0"
              :max="100"
              :step="1"
              :precision="0"
              style="width: 160px"
            />
            <div class="threshold-preset-group">
              <el-button size="small" plain @click="motionPercentile = 80">P80</el-button>
              <el-button size="small" plain @click="motionPercentile = 90">P90</el-button>
              <el-button size="small" plain @click="motionPercentile = 95">P95</el-button>
            </div>
          </div>
        </div>

        <div class="upload-actions">
          <el-button type="primary" :loading="uploading" @click="submitUpload" :disabled="!pendingFiles.length || isMediaProcessing">
            开始上传 ({{ pendingFiles.length }} 个文件)
          </el-button>
        </div>
      </div>

      <div v-if="totalFrames === 0 || !metadataConfirmed" class="metadata-step-card">
        <div class="metadata-step-head">
          <span class="metadata-step-title">步骤 2：填写任务元信息并确认</span>
          <el-tag :type="metadataConfirmed ? 'success' : 'warning'">
            {{ metadataConfirmed ? '已确认' : '待确认' }}
          </el-tag>
        </div>
        <p class="metadata-step-desc">
          请填写比赛日期、比赛名称，并补充选手信息（姓名必填，性别/年龄/身高可选）。支持 1 到 2 位选手。
        </p>

        <el-form label-position="top" class="metadata-form">
          <el-form-item label="比赛日期（必填）">
            <el-date-picker
              v-model="metadataForm.match_date"
              type="date"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              placeholder="选择比赛日期"
              style="width: 100%"
              clearable
            />
          </el-form-item>
          <el-form-item label="比赛名称（必填）">
            <el-input v-model="metadataForm.match_name" maxlength="256" show-word-limit placeholder="例如：2026 校际羽毛球联赛" />
          </el-form-item>

          <div class="metadata-player-head">
            <span>选手信息</span>
            <el-button size="small" type="primary" plain :disabled="metadataForm.players.length >= 2" @click="addPlayer">
              + 添加选手
            </el-button>
          </div>

          <div class="metadata-player-list">
            <div v-for="(player, idx) in metadataForm.players" :key="idx" class="metadata-player-card">
              <div class="metadata-player-title-row">
                <span class="metadata-player-title">选手 {{ idx + 1 }}</span>
                <el-button size="small" text type="danger" @click="removePlayer(idx)">移除</el-button>
              </div>
              <el-row :gutter="10">
                <el-col :xs="24" :sm="12">
                  <el-form-item label="姓名（必填）">
                    <el-input v-model="player.name" maxlength="128" placeholder="如：张三" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="性别（可选）">
                    <el-select v-model="player.gender" clearable placeholder="请选择">
                      <el-option label="男" value="male" />
                      <el-option label="女" value="female" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="年龄（可选）">
                    <el-input-number v-model="player.age" :min="1" :max="99" controls-position="right" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="身高 cm（可选）">
                    <el-input-number v-model="player.height_cm" :min="80" :max="260" controls-position="right" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>
          </div>
        </el-form>

        <div class="metadata-actions">
          <el-button :loading="metadataSaving" @click="saveBatchMetadata">保存元信息</el-button>
          <el-button type="success" :loading="metadataConfirming" @click="confirmBatchMetadata">
            确认并开始标注
          </el-button>
        </div>
      </div>

      <template v-else-if="canAnnotate">
        <div class="annotate-layout">
          <div class="annotate-left">
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
                <div class="annotation-overlay" v-if="currentAnnotation || selectedPlayerLabel || form.action_type || form.action_phase || form.quality_rating">
                  <div class="overlay-tags">
                    <el-tag v-if="selectedPlayerLabel" type="info" size="small">{{ selectedPlayerLabel }}</el-tag>
                    <el-tag v-if="form.action_type" type="primary" size="small">{{ actionTypeLabel(form.action_type) }}</el-tag>
                    <el-tag v-if="form.action_phase" type="success" size="small">{{ actionPhaseLabel(form.action_phase) }}</el-tag>
                    <el-tag v-if="form.quality_rating" type="warning" size="small">{{ qualityLabel(form.quality_rating) }}</el-tag>
                    <el-tag v-if="form.is_forced_action" type="danger" size="small">受迫性动作</el-tag>
                    <el-tag v-if="hasBBox" type="success" size="small">人物框已标注</el-tag>
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
              <el-button size="small" type="info" plain :disabled="isMediaProcessing" @click="showReUpload = true">重新上传图片/视频</el-button>
            </div>
          </div>

          <div class="annotate-right">
            <el-form label-width="90px" label-position="top" class="annotation-form">
              <el-form-item label="选手（必选）">
                <el-select v-model="form.selected_player_id" placeholder="选择选手" style="width: 100%;">
                  <el-option v-for="opt in annotationPlayerOptions" :key="opt.id" :label="opt.label" :value="opt.id" />
                </el-select>
              </el-form-item>

              <el-form-item label="动作类型（必选）">
                <el-select v-model="form.action_type" placeholder="选择动作类型" style="width: 100%;">
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

              <el-form-item label="受迫性动作">
                <el-radio-group v-model="form.is_forced_action">
                  <el-radio :label="false">否</el-radio>
                  <el-radio :label="true">是</el-radio>
                </el-radio-group>
              </el-form-item>

              <el-form-item label="备注">
                <el-input v-model="form.notes" type="textarea" :rows="3" placeholder="可选备注" />
              </el-form-item>

              <el-divider />
              <el-form-item label="标注图层">
                <div class="layer-mode-actions">
                  <el-button :type="annotationLayerMode === 'skeleton' ? 'primary' : undefined" @click="switchToSkeletonMode">标注骨架图</el-button>
                  <el-button :type="annotationLayerMode === 'box' ? 'primary' : undefined" @click="startBoxAnnotation">开始标注Box</el-button>
                  <el-button plain @click="clearBBox" :disabled="!hasBBox">清除Box</el-button>
                </div>
                <div class="keypoint-hint" v-if="annotationLayerMode === 'box'">
                  在左侧图片上按下并拖拽鼠标画出矩形框，松开即完成。
                </div>
              </el-form-item>

              <el-divider />
              <el-form-item label="关键点标注（25 点）" v-if="annotationLayerMode === 'skeleton'">
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
          </div>
        </div>
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
const VIDEO_CHUNK_SIZE = 8 * 1024 * 1024
const chunkUploadActive = ref(false)
const chunkUploadedCount = ref(0)
const chunkTotalCount = ref(0)
const chunkUploadPercent = ref(0)
const chunkUploadETA = ref('')

const useYoloFilter = ref(false)
const motionPercentile = ref(90)

type PlayerMeta = {
  id?: number
  uuid?: string
  name: string
  gender: 'male' | 'female' | ''
  age: number | null
  height_cm: number | null
}

function createEmptyPlayer(): PlayerMeta {
  return { name: '', gender: '', age: null, height_cm: null }
}

const metadataForm = reactive({
  match_date: '',
  match_name: '',
  players: [createEmptyPlayer()] as PlayerMeta[],
})
const metadataConfirmed = ref(false)
const metadataSaving = ref(false)
const metadataConfirming = ref(false)
const mediaProcessStatus = ref<'idle' | 'queued' | 'processing' | 'completed' | 'failed'>('idle')
const mediaProcessMessage = ref('')
const mediaProcessStartedAt = ref<string | null>(null)
const mediaProcessFinishedAt = ref<string | null>(null)
let mediaStatusPollTimer: number | null = null

const isVideoSelected = computed(
  () =>
    pendingFiles.value.length === 1 &&
    /\.(mp4|avi|mov|mkv|webm|flv)$/i.test(pendingFiles.value[0]?.name || ''),
)
const isMediaProcessing = computed(
  () => mediaProcessStatus.value === 'queued' || mediaProcessStatus.value === 'processing',
)
const hasUploadedMedia = computed(
  () => totalFrames.value > 0 || mediaProcessStatus.value !== 'idle',
)
const metadataReady = computed(
  () => !!metadataForm.match_date && !!metadataForm.match_name.trim() && metadataForm.players.some((p) => !!p.name.trim()),
)
const canAnnotate = computed(
  () => totalFrames.value > 0 && metadataConfirmed.value,
)
const annotationPlayerOptions = computed(() =>
  metadataForm.players
    .map((p, idx) => {
      const id = Number(p.id)
      if (!Number.isFinite(id)) return null
      const name = p.name.trim() || `选手${idx + 1}`
      const tags = [
        p.gender === 'male' ? '男' : p.gender === 'female' ? '女' : '',
        p.age ? `${p.age}岁` : '',
        p.height_cm ? `${p.height_cm}cm` : '',
      ].filter(Boolean)
      const label = tags.length ? `${name}（${tags.join(' / ')}）` : name
      return { id, label }
    })
    .filter((p): p is { id: number; label: string } => !!p),
)
const selectedPlayerLabel = computed(() => {
  const id = form.selected_player_id
  if (!id) return ''
  const found = annotationPlayerOptions.value.find((p) => p.id === id)
  return found?.label || ''
})
const mediaProcessTitle = computed(() => {
  if (mediaProcessStatus.value === 'queued') return '视频已上传，等待后台处理'
  if (mediaProcessStatus.value === 'processing') return '视频正在后台处理中'
  if (mediaProcessStatus.value === 'completed') return '媒体处理完成'
  if (mediaProcessStatus.value === 'failed') return '媒体处理失败'
  return ''
})
const mediaProcessAlertType = computed(() => {
  if (mediaProcessStatus.value === 'failed') return 'error'
  if (mediaProcessStatus.value === 'completed') return 'success'
  return 'info'
})

const form = reactive({
  selected_player_id: null as number | null,
  action_type: '',
  action_phase: '',
  quality_rating: '',
  is_forced_action: false,
  notes: '',
  box_x: null as number | null,
  box_y: null as number | null,
  box_w: null as number | null,
  box_h: null as number | null,
})

const annotationLayerMode = ref<'skeleton' | 'box'>('skeleton')
const isDrawingBox = ref(false)
const draftBox = ref<{ x1: number; y1: number; x2: number; y2: number } | null>(null)
const hasBBox = computed(
  () => form.box_x !== null && form.box_y !== null && form.box_w !== null && form.box_h !== null && form.box_w > 0 && form.box_h > 0,
)

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

function applyMediaProcessState(data: any) {
  mediaProcessStatus.value = (data?.media_process_status || 'idle') as typeof mediaProcessStatus.value
  mediaProcessMessage.value = data?.media_process_message || ''
  mediaProcessStartedAt.value = data?.media_process_started_at || null
  mediaProcessFinishedAt.value = data?.media_process_finished_at || null
}

function applyBatchMetadataState(data: any) {
  metadataForm.match_date = data?.match_date || ''
  metadataForm.match_name = data?.match_name || ''
  const players = Array.isArray(data?.players) ? data.players : []
  const normalized = players
    .slice(0, 2)
    .map((p: any) => ({
      id: Number.isInteger(p?.id) ? p.id : undefined,
      uuid: typeof p?.uuid === 'string' ? p.uuid : undefined,
      name: typeof p?.name === 'string' ? p.name : '',
      gender: p?.gender === 'male' || p?.gender === 'female' ? p.gender : '',
      age: Number.isInteger(p?.age) ? p.age : null,
      height_cm: Number.isInteger(p?.height_cm) ? p.height_cm : null,
    }))
  metadataForm.players = normalized.length ? normalized : [createEmptyPlayer()]
  metadataConfirmed.value = !!data?.metadata_confirmed
}

function addPlayer() {
  if (metadataForm.players.length >= 2) return
  metadataForm.players.push(createEmptyPlayer())
}

function removePlayer(index: number) {
  if (metadataForm.players.length <= 1) {
    metadataForm.players[0] = createEmptyPlayer()
    return
  }
  metadataForm.players.splice(index, 1)
}

function buildMetadataPlayersPayload() {
  return metadataForm.players
    .slice(0, 2)
    .map((p) => ({
      id: Number.isInteger(p.id) ? p.id : undefined,
      uuid: p.uuid || undefined,
      name: p.name.trim() || undefined,
      gender: p.gender || undefined,
      age: Number.isInteger(p.age) ? p.age ?? undefined : undefined,
      height_cm: Number.isInteger(p.height_cm) ? p.height_cm ?? undefined : undefined,
    }))
    .filter((p) => p.name)
}

function stopMediaStatusPolling() {
  if (mediaStatusPollTimer !== null) {
    window.clearInterval(mediaStatusPollTimer)
    mediaStatusPollTimer = null
  }
}

function startMediaStatusPolling() {
  if (mediaStatusPollTimer !== null) return
  mediaStatusPollTimer = window.setInterval(() => {
    void refreshMediaProcessStatus()
  }, 3000)
}

async function refreshMediaProcessStatus() {
  try {
    const prevStatus = mediaProcessStatus.value
    const res = await taskApi.getMediaProcessStatus(batchId)
    applyMediaProcessState(res.data)
    if (isMediaProcessing.value) {
      return
    }
    stopMediaStatusPolling()
    if (prevStatus !== mediaProcessStatus.value && mediaProcessStatus.value === 'completed') {
      await loadBatchInfo()
      if (canAnnotate.value) {
        await jumpToFirstUnannotatedFrame()
        await loadAnnotation()
      }
      ElMessage.success(mediaProcessMessage.value || '视频处理完成')
    }
    if (prevStatus !== mediaProcessStatus.value && mediaProcessStatus.value === 'failed') {
      ElMessage.error(mediaProcessMessage.value || '视频处理失败')
    }
  } catch {
    stopMediaStatusPolling()
  }
}

async function loadBatchInfo() {
  try {
    const res = await taskApi.get(batchId)
    batchName.value = res.data.name
    applyMediaProcessState(res.data)
    applyBatchMetadataState(res.data)
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

function onImageError() {
  revokeFrameImageUrl()
  loadingImage.value = false
}

async function loadFrameImage() {
  if (totalFrames.value < 1 || currentFrame.value < 1) return
  revokeFrameImageUrl()
  loadingImage.value = true
  try {
    const url = taskApi.getFrameImageUrl(batchId, currentFrame.value)
    const res = await request.get(url, { responseType: 'blob' })
    frameImageUrl.value = URL.createObjectURL(res.data)
  } catch { /* handled */ }
  finally { loadingImage.value = false }
}

async function loadAnnotation() {
  try {
    const res = await annotationApi.list(batchId, { frame_index: currentFrame.value })
    if (res.data && res.data.length > 0) {
      currentAnnotation.value = res.data[0]
      form.selected_player_id = Number.isInteger(res.data[0].selected_player_id) ? res.data[0].selected_player_id : null
      form.action_type = res.data[0].action_type || ''
      form.action_phase = res.data[0].action_phase || ''
      form.quality_rating = res.data[0].quality_rating || ''
      form.is_forced_action = !!res.data[0].is_forced_action
      form.notes = res.data[0].notes || ''
      form.box_x = typeof res.data[0].box_x === 'number' ? res.data[0].box_x : null
      form.box_y = typeof res.data[0].box_y === 'number' ? res.data[0].box_y : null
      form.box_w = typeof res.data[0].box_w === 'number' ? res.data[0].box_w : null
      form.box_h = typeof res.data[0].box_h === 'number' ? res.data[0].box_h : null
      keypointsList.value = keypointsFromApi(res.data[0].keypoints)
    } else {
      currentAnnotation.value = null
      form.selected_player_id = null
      form.action_type = ''
      form.action_phase = ''
      form.quality_rating = ''
      form.is_forced_action = false
      form.notes = ''
      form.box_x = null
      form.box_y = null
      form.box_w = null
      form.box_h = null
      keypointsList.value = createEmptyKeypoints()
    }
  } catch { /* handled */ }
  await loadFrameImage()
}

async function loadAnnotatedCount(): Promise<Set<number>> {
  try {
    const res = await annotationApi.list(batchId, { limit: 2000 })
    const frames: Set<number> = new Set((res.data || []).map((a: any) => Number(a.frame_index)))
    annotatedCount.value = frames.size
    return frames
  } catch {
    return new Set<number>()
  }
}

async function jumpToFirstUnannotatedFrame() {
  if (totalFrames.value <= 0) return
  const annotatedFrames = await loadAnnotatedCount()
  let targetFrame = 1
  for (let i = 1; i <= totalFrames.value; i++) {
    if (!annotatedFrames.has(i)) {
      targetFrame = i
      break
    }
  }
  currentFrame.value = targetFrame
}

function getKeypointsPayload() {
  return keypointsList.value.filter((kp) => kp.visibility > 0).map((kp) => ({ name: kp.name, x: kp.x, y: kp.y, visibility: kp.visibility }))
}

async function saveAnnotation() {
  if (!form.selected_player_id) {
    ElMessage.warning('请选择选手')
    return
  }
  if (!form.action_type) {
    ElMessage.warning('请选择动作类型')
    return
  }

  saving.value = true
  try {
    const kpPayload = getKeypointsPayload()
    if (currentAnnotation.value) {
      await annotationApi.update(currentAnnotation.value.id, {
        keypoints: kpPayload.length ? kpPayload : null,
        box_x: form.box_x,
        box_y: form.box_y,
        box_w: form.box_w,
        box_h: form.box_h,
        selected_player_id: form.selected_player_id,
        action_type: form.action_type || null,
        action_phase: form.action_phase || null,
        quality_rating: form.quality_rating || null,
        is_forced_action: form.is_forced_action,
        notes: form.notes || null,
      })
      ElMessage.success('标注已更新')
    } else {
      await annotationApi.create({
        task_batch_id: batchId,
        frame_index: currentFrame.value,
        keypoints: kpPayload.length ? kpPayload : null,
        box_x: form.box_x,
        box_y: form.box_y,
        box_w: form.box_w,
        box_h: form.box_h,
        selected_player_id: form.selected_player_id,
        action_type: form.action_type || null,
        action_phase: form.action_phase || null,
        quality_rating: form.quality_rating || null,
        is_forced_action: form.is_forced_action,
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

function generateHash(str: string) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return "up_" + (hash >>> 0).toString(16).padStart(8, '0');
}

async function uploadVideoInChunks(file: File) {
  const totalChunks = Math.max(1, Math.ceil(file.size / VIDEO_CHUNK_SIZE))
  const rawId = `${file.name}_${file.size}_${file.lastModified}`
  // 使用简单的哈希生成 uploadId 兼容 HTTP 环境
  const uploadId = `${generateHash(file.name)}_${file.size}_${file.lastModified}`.replace(/[^a-zA-Z0-9_\-=+/]/g, '_')
  let finalResponse: any = null

  let uploadedChunks = new Set<number>()
  try {
    const res = await taskApi.getUploadedChunks(batchId, uploadId)
    uploadedChunks = new Set(res.data.uploaded_chunks || [])
  } catch {
    // 获取失败或不存在时忽略
  }

  chunkUploadActive.value = true
  chunkTotalCount.value = totalChunks
  chunkUploadedCount.value = uploadedChunks.size
  chunkUploadPercent.value = Math.min(100, Math.round((uploadedChunks.size / totalChunks) * 100))
  chunkUploadETA.value = '计算中...'

  const startTime = Date.now()
  let newlyUploaded = 0

  for (let index = 0; index < totalChunks; index++) {
    // 已经上传直接跳过（但最后一块如果是为了触发合并，则前端仍重新发一次）
    if (uploadedChunks.has(index) && index !== totalChunks - 1) {
      continue
    }

    const start = index * VIDEO_CHUNK_SIZE
    const end = Math.min(start + VIDEO_CHUNK_SIZE, file.size)
    const piece = file.slice(start, end)

    const formData = new FormData()
    formData.append('chunk', piece, file.name)
    formData.append('upload_id', uploadId)
    formData.append('chunk_index', String(index))
    formData.append('total_chunks', String(totalChunks))
    formData.append('original_filename', file.name)
    formData.append('use_yolo_filter', String(useYoloFilter.value))
    if (useYoloFilter.value) {
      formData.append('motion_percentile', String(motionPercentile.value))
    }

    finalResponse = await taskApi.upload(batchId, formData)
    if (!uploadedChunks.has(index)) {
      uploadedChunks.add(index)
    }
    newlyUploaded++
    chunkUploadedCount.value = uploadedChunks.size
    chunkUploadPercent.value = Math.min(100, Math.round((chunkUploadedCount.value / totalChunks) * 100))
    
    const elapsed = (Date.now() - startTime) / 1000
    const avgTimePerChunk = elapsed / newlyUploaded
    const remainingChunks = totalChunks - chunkUploadedCount.value
    if (remainingChunks > 0) {
      const etaSeconds = Math.round(avgTimePerChunk * remainingChunks)
      if (etaSeconds > 60) {
        chunkUploadETA.value = `预计剩余 ${Math.floor(etaSeconds / 60)} 分 ${etaSeconds % 60} 秒`
      } else {
        chunkUploadETA.value = `预计剩余 ${etaSeconds} 秒`
      }
    } else {
      chunkUploadETA.value = '即将完成...'
    }
  }

  return finalResponse
}

async function submitUpload() {
  if (!pendingFiles.value.length || isMediaProcessing.value) return
  const isVideo = pendingFiles.value.length === 1 && /\.(mp4|avi|mov|mkv|webm|flv)$/i.test(pendingFiles.value[0].name || '')
  uploading.value = true
  try {
    let res: any
    if (isVideo) {
      const video = pendingFiles.value[0].raw
      if (!video) {
        ElMessage.warning('视频文件无效，请重新选择')
        return
      }
      res = await uploadVideoInChunks(video)
    } else {
      const formData = new FormData()
      pendingFiles.value.forEach((f) => {
        if (f.raw) formData.append('files', f.raw)
      })
      res = await taskApi.upload(batchId, formData)
    }

    pendingFiles.value = []
    uploadRef.value?.clearFiles()
    if (res.status === 202) {
      mediaProcessStatus.value = 'queued'
      mediaProcessMessage.value = res.data?.message || '视频已上传，正在后台处理中。'
      ElMessage.success(mediaProcessMessage.value)
      startMediaStatusPolling()
      await refreshMediaProcessStatus()
    } else {
      ElMessage.success('上传成功')
      await loadBatchInfo()
      if (canAnnotate.value) {
        await jumpToFirstUnannotatedFrame()
        await loadAnnotation()
      }
    }
  } catch { /* handled */ }
  finally {
    uploading.value = false
    chunkUploadActive.value = false
    chunkUploadedCount.value = 0
    chunkTotalCount.value = 0
    chunkUploadPercent.value = 0
    chunkUploadETA.value = ''
  }
}

async function saveBatchMetadata(showSuccessMessage = true): Promise<boolean> {
  metadataSaving.value = true
  try {
    const players = buildMetadataPlayersPayload()
    const res = await taskApi.updateMetadata(batchId, {
      match_date: metadataForm.match_date || undefined,
      match_name: metadataForm.match_name.trim(),
      players,
    })
    applyBatchMetadataState(res.data)
    if (showSuccessMessage) {
      ElMessage.success('元信息已保存，请继续二次确认')
    }
    return true
  } catch {
    // 错误已由 request 拦截器提示
    return false
  } finally {
    metadataSaving.value = false
  }
}

async function confirmBatchMetadata() {
  if (!hasUploadedMedia.value) {
    ElMessage.warning('请先上传媒体，再确认元信息')
    return
  }

  if (!metadataReady.value) {
    ElMessage.warning('请填写比赛日期、比赛名称，并至少填写一位选手名称')
    return
  }

  metadataConfirming.value = true
  try {
    const saved = await saveBatchMetadata(false)
    if (!saved) return
    const res = await taskApi.confirmMetadata(batchId)
    applyBatchMetadataState(res.data)
    ElMessage.success('元信息确认完成，可以开始标注')
    if (totalFrames.value > 0) {
      await jumpToFirstUnannotatedFrame()
      await loadAnnotation()
    }
  } catch {
    // 错误已由 request 拦截器提示
  } finally {
    metadataConfirming.value = false
  }
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

    if (annotationLayerMode.value === 'box') {
      const drawRect = (
        x: number,
        y: number,
        rw: number,
        rh: number,
        style: { stroke: string; fill: string; label: string; dashed?: boolean; point: string },
      ) => {
        const px = (x / 100) * w
        const py = (y / 100) * h
        const pw = (rw / 100) * w
        const ph = (rh / 100) * h

        // 半透明填充先铺底，让框在复杂背景上也更容易识别。
        ctx.fillStyle = style.fill
        ctx.fillRect(px, py, pw, ph)

        ctx.save()
        ctx.shadowColor = style.stroke
        ctx.shadowBlur = 10
        ctx.strokeStyle = style.stroke
        ctx.lineWidth = 3
        if (style.dashed) {
          ctx.setLineDash([8, 5])
        } else {
          ctx.setLineDash([])
        }
        ctx.strokeRect(px, py, pw, ph)
        ctx.restore()
        ctx.setLineDash([])

        const anchorR = 4
        const corners = [
          [px, py],
          [px + pw, py],
          [px, py + ph],
          [px + pw, py + ph],
        ]
        for (const [cx, cy] of corners) {
          ctx.beginPath()
          ctx.fillStyle = style.point
          ctx.strokeStyle = '#ffffff'
          ctx.lineWidth = 1.5
          ctx.arc(cx, cy, anchorR, 0, Math.PI * 2)
          ctx.fill()
          ctx.stroke()
        }

        const labelText = style.label
        ctx.font = '600 12px "Microsoft YaHei", sans-serif'
        const padX = 8
        const labelW = ctx.measureText(labelText).width + padX * 2
        const labelH = 20
        const labelX = px
        const labelY = Math.max(0, py - labelH - 4)
        ctx.fillStyle = style.stroke
        ctx.fillRect(labelX, labelY, labelW, labelH)
        ctx.fillStyle = '#ffffff'
        ctx.fillText(labelText, labelX + padX, labelY + 14)
      }

      if (hasBBox.value) {
        drawRect(form.box_x as number, form.box_y as number, form.box_w as number, form.box_h as number, {
          stroke: '#22c55e',
          fill: 'rgba(34, 197, 94, 0.18)',
          point: '#22c55e',
          label: '人物框',
        })
      }

      if (draftBox.value) {
        const x = Math.min(draftBox.value.x1, draftBox.value.x2)
        const y = Math.min(draftBox.value.y1, draftBox.value.y2)
        const rw = Math.abs(draftBox.value.x2 - draftBox.value.x1)
        const rh = Math.abs(draftBox.value.y2 - draftBox.value.y1)
        drawRect(x, y, rw, rh, {
          stroke: '#f59e0b',
          fill: 'rgba(245, 158, 11, 0.18)',
          point: '#f59e0b',
          label: '框选中',
          dashed: true,
        })
      }
      return
    }

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
  if (annotationLayerMode.value === 'box') return
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

  if (annotationLayerMode.value === 'box') {
    const rect = canvas.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 100
    const y = ((e.clientY - rect.top) / rect.height) * 100
    isDrawingBox.value = true
    draftBox.value = { x1: x, y1: y, x2: x, y2: y }
    drawKeypointsCanvas()
    return
  }

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
  if (annotationLayerMode.value === 'box') {
    if (!isDrawingBox.value || !draftBox.value) return
    const canvas = canvasRef.value
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    draftBox.value = {
      ...draftBox.value,
      x2: ((e.clientX - rect.left) / rect.width) * 100,
      y2: ((e.clientY - rect.top) / rect.height) * 100,
    }
    drawKeypointsCanvas()
    return
  }

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
  if (annotationLayerMode.value === 'box') {
    if (isDrawingBox.value && draftBox.value) {
      const x = Math.max(0, Math.min(100, Math.min(draftBox.value.x1, draftBox.value.x2)))
      const y = Math.max(0, Math.min(100, Math.min(draftBox.value.y1, draftBox.value.y2)))
      const rw = Math.max(0, Math.min(100, Math.abs(draftBox.value.x2 - draftBox.value.x1)))
      const rh = Math.max(0, Math.min(100, Math.abs(draftBox.value.y2 - draftBox.value.y1)))
      if (rw >= 0.5 && rh >= 0.5) {
        form.box_x = Number(x.toFixed(2))
        form.box_y = Number(y.toFixed(2))
        form.box_w = Number(rw.toFixed(2))
        form.box_h = Number(rh.toFixed(2))
        ElMessage.success('人物框标注完成')
      }
    }
    isDrawingBox.value = false
    draftBox.value = null
    // Stay in box mode after mouse release; user chooses when to switch mode.
    // This avoids accidental keypoint placement caused by the trailing click event.
    drawKeypointsCanvas()
    return
  }

  draggingPointIndex.value = null
}

function startBoxAnnotation() {
  annotationLayerMode.value = 'box'
  draftBox.value = null
  isDrawingBox.value = false
  drawKeypointsCanvas()
}

function switchToSkeletonMode() {
  annotationLayerMode.value = 'skeleton'
  draftBox.value = null
  isDrawingBox.value = false
  drawKeypointsCanvas()
}

function clearBBox() {
  form.box_x = null
  form.box_y = null
  form.box_w = null
  form.box_h = null
  draftBox.value = null
  isDrawingBox.value = false
  drawKeypointsCanvas()
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
  if (!canAnnotate.value) return
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
watch(
  () => [form.box_x, form.box_y, form.box_w, form.box_h, annotationLayerMode.value],
  () => drawKeypointsCanvas(),
)
onMounted(async () => {
  await loadBatchInfo()
  if (isMediaProcessing.value) {
    startMediaStatusPolling()
  }
  if (canAnnotate.value) {
    await jumpToFirstUnannotatedFrame()
    await loadAnnotation()
  }
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  stopMediaStatusPolling()
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
.yolo-settings-card {
  margin-top: 14px;
  padding: 14px 16px;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  background: linear-gradient(180deg, #f5f9ff 0%, #f8fbff 100%);
}
.yolo-settings-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.yolo-settings-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
}
.yolo-settings-desc {
  margin: 8px 0 0;
  font-size: 12px;
  color: #5f6b7a;
}
.threshold-controls {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.threshold-label {
  font-size: 13px;
  color: #334155;
}
.threshold-preset-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.upload-actions {
  margin-top: 16px;
}

.chunk-upload-progress {
  margin: -4px 0 16px;
  padding: 12px 14px;
  border: 1px solid #e6efff;
  border-radius: 8px;
  background: #f8fbff;
}
.chunk-upload-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.chunk-upload-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2d3d;
}
.chunk-upload-meta {
  font-size: 12px;
  color: #5f6b7a;
}
.chunk-eta {
  margin-left: 8px;
  color: #909399;
}

.metadata-step-card {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
}
.metadata-step-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.metadata-step-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.metadata-step-desc {
  margin: 8px 0 12px;
  font-size: 13px;
  color: #606266;
}
.metadata-form {
  max-width: 560px;
}
.metadata-player-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.metadata-player-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.metadata-player-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px 12px 2px;
  background: #fcfdff;
}
.metadata-player-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.metadata-player-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.metadata-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.annotate-layout {
  display: flex;
  height: calc(100vh - 180px);
  gap: 20px;
}

.annotate-left {
  flex: 0 0 66.666%;
  display: flex;
  flex-direction: column;
}

.annotate-right {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.frame-area {
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  flex: 1;
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
.layer-mode-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
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
