<template>
  <div>
    <el-card>
      <template #header><span>数据导出</span></template>
      <el-form label-width="100px" style="max-width: 600px;">
        <el-form-item label="选择项目">
          <el-select v-model="selectedProject" placeholder="请选择项目" style="width: 100%;">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="导出格式">
          <el-radio-group v-model="format">
            <el-radio-button value="coco">COCO 关键点</el-radio-button>
            <el-radio-button value="csv">CSV 表格</el-radio-button>
            <el-radio-button value="vlm">VLM 提示词</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="仅已锁定">
          <el-switch v-model="onlyLocked" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="exporting" @click="doExport">导出预览</el-button>
          <el-button type="success" :loading="downloading" @click="doDownload">下载文件</el-button>
        </el-form-item>
      </el-form>

      <el-divider v-if="exportResult" />
      <el-descriptions v-if="exportResult" :column="3" border>
        <el-descriptions-item label="文件名">{{ exportResult.filename }}</el-descriptions-item>
        <el-descriptions-item label="格式">{{ exportResult.format }}</el-descriptions-item>
        <el-descriptions-item label="记录数">{{ exportResult.record_count }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { projectApi, exportApi } from '@/api'
import { ElMessage } from 'element-plus'

const projects = ref<any[]>([])
const selectedProject = ref<number | null>(null)
const format = ref('coco')
const onlyLocked = ref(true)
const exporting = ref(false)
const downloading = ref(false)
const exportResult = ref<any>(null)

async function loadProjects() {
  const res = await projectApi.list()
  projects.value = res.data
}

async function doExport() {
  if (!selectedProject.value) { ElMessage.warning('请选择项目'); return }
  exporting.value = true
  try {
    const res = await exportApi.export(selectedProject.value, { format: format.value, only_locked: onlyLocked.value })
    exportResult.value = res.data
    ElMessage.success('导出预览完成')
  } catch { /* handled */ }
  finally { exporting.value = false }
}

async function doDownload() {
  if (!selectedProject.value) { ElMessage.warning('请选择项目'); return }
  downloading.value = true
  try {
    const res = await exportApi.download(selectedProject.value, { format: format.value, only_locked: onlyLocked.value })
    const blob = new Blob([res.data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `project_${selectedProject.value}_${format.value}.${format.value === 'csv' ? 'csv' : 'json'}`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch { /* handled */ }
  finally { downloading.value = false }
}

onMounted(loadProjects)
</script>
