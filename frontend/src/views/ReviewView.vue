<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>审核流程</span>
          <el-select v-model="statusFilter" placeholder="按状态筛选" clearable style="width: 180px;">
            <el-option label="自核中" value="self_review" />
            <el-option label="组长核对" value="leader_review" />
            <el-option label="专家终审" value="expert_review" />
          </el-select>
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
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showRejectDialog" title="打回原因" width="400px">
      <el-input v-model="rejectComment" type="textarea" rows="3" placeholder="请填写打回原因" />
      <template #footer>
        <el-button @click="showRejectDialog = false">取消</el-button>
        <el-button type="danger" @click="doReject">确定打回</el-button>
      </template>
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
import { taskApi, reviewApi } from '@/api'
import { ElMessage } from 'element-plus'

const tasks = ref<any[]>([])
const loading = ref(false)
const statusFilter = ref('')
const showRejectDialog = ref(false)
const rejectComment = ref('')
const rejectTaskId = ref(0)
const showHistoryDialog = ref(false)
const historyRecords = ref<any[]>([])

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

onMounted(loadTasks)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
