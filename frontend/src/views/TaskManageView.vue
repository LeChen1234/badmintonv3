<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>任务管理</span>
          <div>
            <el-select v-model="filterProject" placeholder="按项目筛选" clearable style="width: 200px; margin-right: 12px;">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
            <el-button type="primary" @click="showCreateDialog = true">新建任务批次</el-button>
          </div>
        </div>
      </template>
      <el-table :data="tasks" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="批次名称" />
        <el-table-column prop="action_category" label="动作类别" width="100" />
        <el-table-column prop="assignee_name" label="负责人" width="100" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="120">
          <template #default="{ row }">
            {{ row.completed_frames }} / {{ row.total_frames }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300">
          <template #default="{ row }">
            <el-button size="small" @click="openAssign(row)">分配</el-button>
            <el-button size="small" type="warning" @click="triggerMl(row.id)"
              :disabled="!mlEnabled" :title="mlEnabled ? 'ML 初标' : '大模型标注未启用'">
              ML 初标(可选)
            </el-button>
            <el-button size="small" type="success" @click="goAnnotate(row)">标注</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showCreateDialog" title="新建任务批次" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="项目">
          <el-select v-model="form.project_id" placeholder="选择项目">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="批次名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="动作类别">
          <el-input v-model="form.action_category" placeholder="如: smash, clear" />
        </el-form-item>
        <el-form-item label="总帧数">
          <el-input-number v-model="form.total_frames" :min="0" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="form.assigned_to" placeholder="选择负责人" clearable>
            <el-option v-for="u in students" :key="u.id" :label="u.display_name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="form.deadline" type="datetime" placeholder="选择截止时间" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createBatch">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showAssignDialog" title="分配任务" width="400px">
      <el-select v-model="assignUserId" placeholder="选择标注员" style="width: 100%;">
        <el-option v-for="u in students" :key="u.id" :label="u.display_name" :value="u.id" />
      </el-select>
      <template #footer>
        <el-button @click="showAssignDialog = false">取消</el-button>
        <el-button type="primary" @click="doAssign">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { taskApi, projectApi, userApi } from '@/api'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

const router = useRouter()
const mlEnabled = ref(false)

const tasks = ref<any[]>([])
const projects = ref<any[]>([])
const students = ref<any[]>([])
const loading = ref(false)
const filterProject = ref<number | null>(null)
const showCreateDialog = ref(false)
const showAssignDialog = ref(false)
const assignBatchId = ref(0)
const assignUserId = ref<number | null>(null)

const form = reactive({
  project_id: null as number | null,
  name: '',
  action_category: '',
  total_frames: 0,
  assigned_to: null as number | null,
  deadline: null as string | null,
})

const statusMap: Record<string, string> = {
  pending: '待分配', annotating: '标注中', self_review: '自核中',
  leader_review: '组长核对', expert_review: '专家终审', locked: '已锁定',
}
const statusLabel = (s: string) => statusMap[s] || s
const statusType = (s: string) =>
  ({ pending: 'info', annotating: '', self_review: 'warning', leader_review: 'warning', expert_review: 'warning', locked: 'success' }[s] || '')

async function loadTasks() {
  loading.value = true
  try {
    const params: any = {}
    if (filterProject.value) params.project_id = filterProject.value
    const res = await taskApi.list(params)
    tasks.value = res.data
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  const res = await projectApi.list()
  projects.value = res.data
}

async function loadStudents() {
  const res = await userApi.list()
  students.value = res.data
}

async function createBatch() {
  try {
    await taskApi.create(form)
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    loadTasks()
  } catch { /* handled */ }
}

function openAssign(row: any) {
  assignBatchId.value = row.id
  assignUserId.value = row.assigned_to
  showAssignDialog.value = true
}

async function doAssign() {
  if (!assignUserId.value) return
  try {
    await taskApi.assign(assignBatchId.value, assignUserId.value)
    ElMessage.success('分配成功')
    showAssignDialog.value = false
    loadTasks()
  } catch { /* handled */ }
}

async function triggerMl(batchId: number) {
  try {
    await taskApi.triggerMl(batchId)
    ElMessage.success('已触发 ML 初标')
  } catch { /* handled */ }
}

function goAnnotate(row: any) {
  router.push(`/annotate/${row.id}`)
}

async function checkMlEnabled() {
  try {
    const res = await request.get('/health')
    mlEnabled.value = res.data?.ml_backend_enabled === true
  } catch { mlEnabled.value = false }
}

watch(filterProject, loadTasks)
onMounted(() => { loadTasks(); loadProjects(); loadStudents(); checkMlEnabled() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
