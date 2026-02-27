<template>
  <div>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card>
          <template #header><span>整体完成率</span></template>
          <div class="progress-center">
            <el-progress type="dashboard" :percentage="overview.overall_completion_rate" :width="180" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card>
          <template #header><span>项目进度概览</span></template>
          <div v-for="p in overview.projects" :key="p.project_id" class="project-row">
            <span class="project-name">{{ p.project_name }}</span>
            <el-progress :percentage="p.completion_rate" :stroke-width="18" text-inside class="project-bar" />
            <span class="project-count">{{ p.locked }}/{{ p.total_batches }}</span>
          </div>
          <el-empty v-if="!overview.projects.length" description="暂无项目" />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 24px;">
      <template #header><span>人员工作量统计</span></template>
      <el-table :data="overview.users" stripe>
        <el-table-column prop="display_name" label="姓名" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            {{ roleLabel(row.role) }}
          </template>
        </el-table-column>
        <el-table-column prop="assigned_batches" label="分配批次" width="100" />
        <el-table-column prop="completed_batches" label="完成批次" width="100" />
        <el-table-column label="完成率" width="200">
          <template #default="{ row }">
            <el-progress :percentage="row.completion_rate" :stroke-width="14" text-inside />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { progressApi } from '@/api'

const overview = reactive({
  total_projects: 0, total_batches: 0, total_locked: 0, overall_completion_rate: 0,
  projects: [] as any[], users: [] as any[],
})

const roleMap: Record<string, string> = { admin: '管理员', expert: '专家', leader: '组长', student: '学生' }
const roleLabel = (r: string) => roleMap[r] || r

onMounted(async () => {
  try {
    const res = await progressApi.overview()
    Object.assign(overview, res.data)
  } catch { /* empty */ }
})
</script>

<style scoped>
.progress-center { display: flex; justify-content: center; padding: 20px 0; }
.project-row { display: flex; align-items: center; margin-bottom: 12px; }
.project-name { width: 140px; font-weight: 500; flex-shrink: 0; }
.project-bar { flex: 1; margin: 0 16px; }
.project-count { width: 60px; text-align: right; color: #909399; font-size: 13px; flex-shrink: 0; }
</style>
