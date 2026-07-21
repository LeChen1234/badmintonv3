<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>审核流程</span>
          <div>
            <el-button type="warning" @click="openExpertQueue">专家判定队列（{{ expertPendingCount }}）</el-button>
            <el-select v-model="statusFilter" placeholder="按状态筛选" clearable style="width: 180px; margin-left: 10px">
            <el-option label="自核中" value="self_review" />
            <el-option label="组长核对" value="leader_review" />
            <el-option label="专家终审" value="expert_review" />
          </el-select>
          </div>
        </div>
      </template>
      <el-table :data="filteredTasks" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="批次名称" />
        <el-table-column prop="assignee_name" label="标注员" width="100" />
        <el-table-column prop="status" label="当前状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300">
          <template #default="{ row }">
            <template v-if="row.status === 'annotating'">
              <el-button size="small" type="primary" @click="submitReview(row.id)">提交审核</el-button>
            </template>
            <template v-if="row.status === 'self_review'">
              <el-button size="small" type="primary" @click="submitReview(row.id)">自核通过</el-button>
            </template>
            <template v-if="['leader_review', 'expert_review'].includes(row.status)">
              <el-button size="small" type="success" @click="approve(row.id)">通过</el-button>
              <el-button size="small" type="danger" @click="openReject(row.id)">打回</el-button>
            </template>
            <el-button size="small" @click="showHistory(row.id)">历史</el-button>
            <el-button size="small" type="warning" @click="showAgreement(row.id)">一致性</el-button>
            <el-button v-if="row.status === 'expert_review'" size="small" type="danger" @click="openAdjudication(row.id)">专家裁决</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showExpertQueue" title="体育专家判定队列" width="900px">
      <el-alert type="info" :closable="false" title="学生已完成人员身份、边界框和关键点；专家只处理下列专业判断，不重复粗标。" />
      <el-table :data="expertQueue" stripe style="margin-top: 14px" max-height="560">
        <el-table-column prop="task_batch_name" label="任务" min-width="150" />
        <el-table-column prop="frame_index" label="帧" width="70" />
        <el-table-column prop="player_name" label="人员" width="110" />
        <el-table-column label="学生粗标" min-width="170">
          <template #default="{ row }">
            {{ row.coarse_context.action_type || '未分类' }} · 可见点 {{ row.coarse_context.visible_keypoints }}/25
          </template>
        </el-table-column>
        <el-table-column label="需要专家判定" min-width="260">
          <template #default="{ row }">{{ (row.reasons || []).join('；') }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openExpertItem(row)">判定</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer><el-button @click="showExpertQueue = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="showRejectDialog" title="打回原因" width="400px">
      <el-input v-model="rejectComment" type="textarea" rows="3" placeholder="请填写打回原因" />
      <template #footer>
        <el-button @click="showRejectDialog = false">取消</el-button>
        <el-button type="danger" @click="doReject">确定打回</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showAdjudicationDialog" title="专家裁决与金标准标注（Gold-standard Annotation）" width="900px" @closed="releaseFrameUrl">
      <el-empty v-if="!disagreements.length" description="暂无待裁决的双标分歧" />
      <template v-else>
        <div class="adjudication-nav">
          <el-button :disabled="disagreementIndex <= 0" @click="selectDisagreement(disagreementIndex - 1)">上一项</el-button>
          <span>第 {{ disagreementIndex + 1 }} / {{ disagreements.length }} 项 · 帧 {{ currentDisagreement?.frame_index }}</span>
          <el-button :disabled="disagreementIndex >= disagreements.length - 1" @click="selectDisagreement(disagreementIndex + 1)">下一项</el-button>
        </div>
        <div class="pose-compare">
          <img v-if="frameImageUrl" :src="frameImageUrl" class="compare-image" />
          <div class="point-layer">
            <template v-for="(candidate, cidx) in (currentDisagreement?.candidates || [])" :key="candidate.annotation_id">
              <span v-for="point in visiblePoints(candidate)" :key="`${candidate.annotation_id}-${point.name}`"
                class="compare-point" :style="{ left: `${point.x}%`, top: `${point.y}%`, background: candidateColor(cidx) }"
                :title="`${candidate.option}: ${point.name}`" />
            </template>
          </div>
        </div>
        <el-radio-group v-model="selectedWinner" class="candidate-grid">
          <el-radio v-for="(candidate, cidx) in (currentDisagreement?.candidates || [])" :key="candidate.annotation_id"
            :value="candidate.annotation_id" border class="candidate-card">
            <span class="candidate-dot" :style="{ background: candidateColor(cidx) }" />
            方案 {{ candidate.option }} · {{ candidate.action_type || '-' }} / {{ candidate.action_phase || '-' }} / {{ candidate.quality_rating || '-' }}
          </el-radio>
        </el-radio-group>
        <el-input v-model="adjudicationComment" type="textarea" :rows="2" placeholder="记录裁决依据或分歧原因" />
      </template>
      <template #footer>
        <el-button @click="showAdjudicationDialog = false">关闭</el-button>
        <el-button type="primary" :disabled="!selectedWinner" :loading="adjudicating" @click="submitAdjudication">确认为 Gold</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showAgreementDialog" title="盲法复标一致性" width="680px">
      <el-alert :type="agreement?.readiness?.ready ? 'success' : 'warning'" :closable="false"
        :title="agreement?.readiness?.ready ? '达到统计门槛' : '复标样本尚未达到协议门槛'" />
      <el-descriptions v-if="agreement" :column="3" border style="margin-top: 16px;">
        <el-descriptions-item label="标注员">{{ agreement.annotator_count }}</el-descriptions-item>
        <el-descriptions-item label="复标项目">{{ agreement.double_annotated_items }}</el-descriptions-item>
        <el-descriptions-item label="可比关键点">{{ agreement.keypoints?.comparable_joints }}</el-descriptions-item>
        <el-descriptions-item label="动作 Kappa">{{ metric(agreement.categorical?.action_type?.kappa) }}</el-descriptions-item>
        <el-descriptions-item label="阶段 Kappa">{{ metric(agreement.categorical?.action_phase?.kappa) }}</el-descriptions-item>
        <el-descriptions-item label="质量 Kappa">{{ metric(agreement.categorical?.quality_rating?.kappa) }}</el-descriptions-item>
        <el-descriptions-item label="PCK@0.05">{{ metric(agreement.keypoints?.pck?.['0.05']) }}</el-descriptions-item>
        <el-descriptions-item label="PCK@0.10">{{ metric(agreement.keypoints?.pck?.['0.1']) }}</el-descriptions-item>
        <el-descriptions-item label="归一化误差">{{ metric(agreement.keypoints?.mean_normalized_error) }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="showHistoryDialog" title="审核历史" width="600px">
      <el-timeline>
        <el-timeline-item v-for="r in historyRecords" :key="r.id"
          :type="r.result === 'pass' ? 'success' : 'danger'" :timestamp="r.created_at">
          <strong>{{ r.reviewer_name }}</strong>
          {{ levelLabel(r.review_level) }} -
          <el-tag :type="r.result === 'pass' ? 'success' : 'danger'" size="small">
            {{ r.result === 'pass' ? '通过' : '打回' }}
          </el-tag>
          <p v-if="r.comment" style="margin: 4px 0 0; color: #606266;">{{ r.comment }}</p>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-if="!historyRecords.length" description="暂无审核记录" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { taskApi, reviewApi } from '@/api'
import { ElMessage } from 'element-plus'

const tasks = ref<any[]>([])
const router = useRouter()
const showExpertQueue = ref(false)
const expertQueue = ref<any[]>([])
const expertPendingCount = ref(0)
const loading = ref(false)
const statusFilter = ref('')
const showRejectDialog = ref(false)
const rejectComment = ref('')
const rejectTaskId = ref(0)
const showHistoryDialog = ref(false)
const historyRecords = ref<any[]>([])
const showAgreementDialog = ref(false)
const agreement = ref<any>(null)
const metric = (value: unknown) => typeof value === 'number' ? value.toFixed(3) : '-'
const showAdjudicationDialog = ref(false)
const disagreementTaskId = ref(0)
const disagreements = ref<any[]>([])
const disagreementIndex = ref(0)
const selectedWinner = ref<number | null>(null)
const adjudicationComment = ref('')
const adjudicating = ref(false)
const frameImageUrl = ref('')
const currentDisagreement = computed(() => disagreements.value[disagreementIndex.value] || null)
const candidateColor = (index: number) => ['#f56c6c', '#409eff', '#67c23a'][index % 3]
const visiblePoints = (candidate: any) => (candidate?.keypoints || []).filter((point: any) => Number(point.visibility || 0) > 0)

const statusMap: Record<string, string> = {
  pending: '待分配', annotating: '标注中', self_review: '自核中',
  leader_review: '组长核对', expert_review: '专家终审', locked: '已锁定',
}
const statusLabel = (s: string) => statusMap[s] || s
const statusType = (s: string) =>
  ({ pending: 'info', annotating: '', self_review: 'warning', leader_review: 'warning', expert_review: 'warning', locked: 'success' }[s] || '')
const levelLabel = (l: string) => ({ self: '自核', leader: '组长核对', expert: '专家终审' }[l] || l)

const filteredTasks = computed(() => {
  if (!statusFilter.value) return tasks.value
  return tasks.value.filter(t => t.status === statusFilter.value)
})

async function loadTasks() {
  loading.value = true
  try {
    const res = await taskApi.list()
    tasks.value = res.data
  } finally {
    loading.value = false
  }
}

async function submitReview(taskId: number) {
  try {
    await reviewApi.submit(taskId)
    ElMessage.success('提交成功')
    loadTasks()
  } catch { /* handled */ }
}

async function approve(taskId: number) {
  try {
    await reviewApi.approve(taskId, { result: 'pass' })
    ElMessage.success('审核通过')
    loadTasks()
  } catch { /* handled */ }
}

function openReject(taskId: number) {
  rejectTaskId.value = taskId
  rejectComment.value = ''
  showRejectDialog.value = true
}

async function doReject() {
  try {
    await reviewApi.reject(rejectTaskId.value, { result: 'reject', comment: rejectComment.value })
    ElMessage.success('已打回')
    showRejectDialog.value = false
    loadTasks()
  } catch { /* handled */ }
}

async function showHistory(taskId: number) {
  try {
    const res = await reviewApi.history(taskId)
    historyRecords.value = res.data
    showHistoryDialog.value = true
  } catch { /* handled */ }
}

async function loadExpertQueue() {
  try {
    const response = await reviewApi.expertQueue()
    expertQueue.value = response.data.items || []
    expertPendingCount.value = Number(response.data.pending_count || 0)
  } catch {
    expertQueue.value = []
  }
}

async function openExpertQueue() {
  await loadExpertQueue()
  showExpertQueue.value = true
}

function openExpertItem(item: any) {
  showExpertQueue.value = false
  router.push({ path: `/annotate/${item.task_batch_id}`, query: { frame: item.frame_index, annotation: item.annotation_id } })
}

async function showAgreement(taskId: number) {
  try {
    const res = await reviewApi.agreement(taskId)
    agreement.value = res.data
    showAgreementDialog.value = true
  } catch { /* handled */ }
}

function releaseFrameUrl() {
  if (frameImageUrl.value) URL.revokeObjectURL(frameImageUrl.value)
  frameImageUrl.value = ''
}

async function selectDisagreement(index: number) {
  disagreementIndex.value = index
  const item = currentDisagreement.value
  selectedWinner.value = item?.candidates?.[0]?.annotation_id || null
  adjudicationComment.value = ''
  releaseFrameUrl()
  if (!item) return
  const response = await taskApi.getFrameImageBlob(disagreementTaskId.value, item.frame_index)
  frameImageUrl.value = URL.createObjectURL(response.data)
}

async function openAdjudication(taskId: number) {
  disagreementTaskId.value = taskId
  const response = await reviewApi.disagreements(taskId)
  disagreements.value = response.data.items || []
  showAdjudicationDialog.value = true
  if (disagreements.value.length) await selectDisagreement(0)
}

async function submitAdjudication() {
  if (!selectedWinner.value) return
  adjudicating.value = true
  try {
    await reviewApi.adjudicate(disagreementTaskId.value, {
      winner_annotation_id: selectedWinner.value,
      comment: adjudicationComment.value || null,
    })
    ElMessage.success('已生成唯一 Gold Annotation')
    const response = await reviewApi.disagreements(disagreementTaskId.value)
    disagreements.value = response.data.items || []
    if (disagreements.value.length) await selectDisagreement(Math.min(disagreementIndex.value, disagreements.value.length - 1))
    else releaseFrameUrl()
  } finally {
    adjudicating.value = false
  }
}

onMounted(() => {
  loadTasks()
  loadExpertQueue()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.adjudication-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.pose-compare { position: relative; width: 100%; min-height: 360px; background: #111; overflow: hidden; }
.compare-image { display: block; width: 100%; max-height: 520px; object-fit: contain; }
.point-layer { position: absolute; inset: 0; }
.compare-point { position: absolute; width: 10px; height: 10px; border: 2px solid white; border-radius: 50%; transform: translate(-50%, -50%); }
.candidate-grid { display: grid; gap: 10px; margin: 14px 0; width: 100%; }
.candidate-card { width: 100%; margin: 0; }
.candidate-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
</style>
