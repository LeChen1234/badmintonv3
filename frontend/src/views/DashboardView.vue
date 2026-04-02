<template>
  <el-card class="dashboard-container">
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6" :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <template #header><span>项目总数</span></template>
          <div class="stat-value">{{ overview.total_projects }}</div>
        </el-card>
      </el-col>
      <el-col :span="6" :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <template #header><span>任务批次</span></template>
          <div class="stat-value">{{ overview.total_batches }}</div>
        </el-card>
      </el-col>
      <el-col :span="6" :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <template #header><span>已完成锁定</span></template>
          <div class="stat-value success">{{ overview.total_locked }}</div>
        </el-card>
      </el-col>
      <el-col :span="6" :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <template #header><span>完成率</span></template>
          <div class="stat-value primary">{{ overview.overall_completion_rate }}%</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="tables-row">
      <el-col :span="12" :xs="24" :sm="12">
        <el-card class="table-card">
          <template #header>
            <div class="card-header">
              <el-icon class="header-icon"><DataAnalysis /></el-icon>
              <span>各项目进度</span>
            </div>
          </template>
          <div class="table-wrapper">
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
          </div>
        </el-card>
      </el-col>
      <el-col :span="12" :xs="24" :sm="12">
        <el-card class="table-card">
          <template #header>
            <div class="card-header">
              <el-icon class="header-icon"><User /></el-icon>
              <span>人员工作量</span>
            </div>
          </template>
          <div class="table-wrapper">
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
          </div>
        </el-card>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { progressApi } from '@/api'
import { DataAnalysis, User } from '@element-plus/icons-vue'

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
.dashboard-container {
  padding: 20px;
  background-color: #fff;
  min-height: 100%;
}

.stats-row {
  margin-bottom: 20px;
}

.stats-row .el-col {
  margin-bottom: 10px;
}

.stat-card {
  border: none;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.stat-card:hover {
  box-shadow: 0 4px 16px 0 rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

.stat-card :deep(.el-card__header) {
  padding: 12px 16px;
  font-size: 14px;
  color: #606266;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}

.stat-card :deep(.el-card__body) {
  padding: 20px 16px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  text-align: center;
  color: #303133;
}

.stat-value.success { 
  color: #67c23a; 
}

.stat-value.primary { 
  color: #409eff; 
}

.tables-row .el-col {
  margin-bottom: 20px;
}

.table-card {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  border: none;
}

.table-card :deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid #ebeef5;
  background: linear-gradient(135deg, #f5f7fa 0%, #fff 100%);
}

.table-card :deep(.el-card__body) {
  padding: 0;
}

.card-header {
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
  color: #333;
}

.card-header .header-icon {
  margin-right: 8px;
  font-size: 18px;
  color: #409eff;
}

.table-wrapper {
  padding: 20px;
}

.table-wrapper :deep(.el-table) {
  --el-table-border-color: #ebeef5;
}

.table-wrapper :deep(.el-table__body-wrapper) {
  max-height: 310px;
  overflow-y: auto;
}

.table-wrapper :deep(.el-table__body-wrapper)::-webkit-scrollbar {
  width: 6px;
}

.table-wrapper :deep(.el-table__body-wrapper)::-webkit-scrollbar-thumb {
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
}

.table-wrapper :deep(.el-table__body-wrapper)::-webkit-scrollbar-thumb:hover {
  background-color: rgba(0, 0, 0, 0.3);
}

.table-wrapper :deep(.el-table__body-wrapper)::-webkit-scrollbar-track {
  background-color: #f5f7fa;
  border-radius: 3px;
}

:deep(.el-table th) {
  background: #f5f7fa;
  font-weight: 600;
  color: #606266;
}

:deep(.el-table td),
:deep(.el-table th) {
  padding: 10px 0;
}

:deep(.el-table .el-progress :deep(.el-progress-bar__outer)) {
  background-color: #ebeef5;
}

@media (max-width: 768px) {
  .dashboard-container {
    padding: 10px;
  }
  
  .stats-row .el-col {
    margin-bottom: 10px;
  }
  
  .tables-row .el-col {
    margin-bottom: 10px;
  }
  
  .table-wrapper :deep(.el-table__body-wrapper) {
    max-height: 260px;
  }
}

@media (max-width: 576px) {
  .stat-value {
    font-size: 28px;
  }
  
  .table-wrapper {
    padding: 12px;
  }
  
  .table-wrapper :deep(.el-table__body-wrapper) {
    max-height: 210px;
  }
}
</style>