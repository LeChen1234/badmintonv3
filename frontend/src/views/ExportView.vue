<template>
  <div>
    <el-card>
      <template #header><span>数据导出 - 已确认标注数据集</span></template>
      <el-alert
        v-if="!canExport"
        type="warning"
        :closable="false"
        title="仅超级管理员可使用导出功能"
        style="margin-bottom: 16px;"
      />
      <el-form label-width="120px" style="max-width: 600px;">
        <el-form-item label="选择项目">
          <el-select v-model="selectedProject" placeholder="请选择项目" style="width: 100%;" @change="loadConfirmedCount">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="导出格式">
          <el-radio-group v-model="exportFormat">
            <el-radio-button value="json">JSON（含标注人）</el-radio-button>
            <el-radio-button value="coco">COCO</el-radio-button>
            <el-radio-button value="csv">CSV</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="研究级过滤">
          <el-switch v-model="onlyLocked" active-text="仅导出已锁定任务" inactive-text="包含未锁定任务" @change="loadConfirmedCount" />
        </el-form-item>
        <el-form-item label="已确认标注数">
          <el-tag type="success" size="large">{{ confirmedCount }} 条</el-tag>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="exporting" @click="doExport">
            导出已确认数据集
          </el-button>
        </el-form-item>
      </el-form>

      <el-divider v-if="exportResult" />
      <el-descriptions v-if="exportResult" :column="3" border>
        <el-descriptions-item label="文件名">{{ exportResult.filename }}</el-descriptions-item>
        <el-descriptions-item label="格式">{{ exportResult.format }}</el-descriptions-item>
        <el-descriptions-item label="记录数">{{ exportResult.record_count }}</el-descriptions-item>
        <el-descriptions-item label="数据集版本">{{ exportResult.dataset_id }}</el-descriptions-item>
        <el-descriptions-item label="内容指纹" :span="2"><code>{{ exportResult.dataset_sha256 }}</code></el-descriptions-item>
        <el-descriptions-item label="研究切分" :span="3">
          训练 {{ exportResult.split_record_counts?.train || 0 }} / 验证 {{ exportResult.split_record_counts?.validation || 0 }} / 测试 {{ exportResult.split_record_counts?.test || 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="论文发布门禁" :span="3">
          <el-tag :type="exportResult.release_ready ? 'success' : 'danger'">
            {{ exportResult.release_ready ? '通过' : '未通过' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <el-alert v-for="warning in (exportResult?.warnings || [])" :key="warning" type="warning" :closable="false" :title="warning" style="margin-top: 12px;" />
      <div v-if="exportResult" style="margin-top: 16px;">
        <el-button type="success" :loading="downloading" @click="doDownload">
          下载导出文件
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { projectApi, exportApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const projects = ref<any[]>([])
const selectedProject = ref<number | null>(null)
const exportFormat = ref<'json' | 'coco' | 'csv'>('json')
const confirmedCount = ref(0)
const onlyLocked = ref(true)
const exporting = ref(false)
const downloading = ref(false)
const exportResult = ref<any>(null)
const authStore = useAuthStore()
const canExport = computed(() => authStore.user?.role === 'super_admin')

async function loadProjects() {
  const res = await projectApi.list()
  projects.value = res.data
}

async function loadConfirmedCount() {
  if (!canExport.value) { confirmedCount.value = 0; return }
  if (!selectedProject.value) { confirmedCount.value = 0; return }
  try {
    const res = await exportApi.confirmedCount(selectedProject.value)
    confirmedCount.value = onlyLocked.value ? res.data.locked_confirmed_count : res.data.confirmed_count
  } catch { confirmedCount.value = 0 }
}

async function doExport() {
  if (!canExport.value) { ElMessage.warning('仅超级管理员可导出数据'); return }
  if (!selectedProject.value) { ElMessage.warning('请选择项目'); return }
  exporting.value = true
  try {
    const res = await exportApi.export(selectedProject.value, { format: exportFormat.value, only_locked: onlyLocked.value })
    exportResult.value = res.data
    ElMessage.success('导出完成，可以下载')
  } catch { /* handled */ }
  finally { exporting.value = false }
}

async function doDownload() {
  if (!canExport.value) { ElMessage.warning('仅超级管理员可下载导出文件'); return }
  if (!exportResult.value?.filename || !selectedProject.value) return
  downloading.value = true
  try {
    const res = await exportApi.download(selectedProject.value, exportResult.value.filename)
    const blob = new Blob([res.data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportResult.value.filename
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch { /* handled */ }
  finally { downloading.value = false }
}

onMounted(async () => {
  await loadProjects()
  if (canExport.value && selectedProject.value) {
    await loadConfirmedCount()
  }
})
</script>
