<template>
  <div class="dashboard">
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header><span>项目总数</span></template>
          <div class="stat-value">{{ overview.total_projects }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header><span>任务批次</span></template>
          <div class="stat-value">{{ overview.total_batches }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header><span>已完成锁定</span></template>
          <div class="stat-value success">{{ overview.total_locked }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header><span>完成率</span></template>
          <div class="stat-value primary">{{ overview.overall_completion_rate }}%</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 24px;">
      <el-col :span="12">
        <el-card>
          <template #header><span>各项目进度</span></template>
          <el-table :data="overview.projects" stripe size="small">
            <el-table-column prop="project_name" label="项目" />
            <el-table-column prop="total_batches" label="总批次" width="80" />
            <el-table-column prop="locked" label="已完成" width="80" />
            <el-table-column label="完成率" width="120">
              <template #default="{ row }">
                <el-progress :percentage="row.completion_rate" :stroke-width="14" text-inside />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header><span>人员工作量</span></template>
          <el-table :data="overview.users" stripe size="small">
            <el-table-column prop="display_name" label="姓名" />
            <el-table-column prop="role" label="角色" width="80" />
            <el-table-column prop="assigned_batches" label="分配" width="60" />
            <el-table-column prop="completed_batches" label="完成" width="60" />
            <el-table-column label="完成率" width="120">
              <template #default="{ row }">
                <el-progress :percentage="row.completion_rate" :stroke-width="14" text-inside />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { progressApi } from '@/api'

const overview = reactive({
  total_projects: 0,
  total_batches: 0,
  total_locked: 0,
  overall_completion_rate: 0,
  projects: [] as any[],
  users: [] as any[],
})

onMounted(async () => {
  try {
    const res = await progressApi.overview()
    Object.assign(overview, res.data)
  } catch { /* empty */ }
})
</script>

<style scoped>
.stat-value {
  font-size: 32px;
  font-weight: 700;
  text-align: center;
  color: #303133;
}
.stat-value.success { color: #67c23a; }
.stat-value.primary { color: #409eff; }
</style>
