<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目管理</span>
          <el-button type="primary" @click="openCreate">新建项目</el-button>
        </div>
      </template>

      <el-table :data="projects" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="项目名称" />
        <el-table-column prop="description" label="描述" min-width="220">
          <template #default="{ row }">
            <span>{{ row.description || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-popconfirm title="确认删除该项目？" @confirm="removeProject(row.id)">
              <template #reference>
                <el-button type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" title="新建项目" width="460px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="项目名称">
          <el-input v-model="form.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="createProject">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { projectApi } from '@/api'
import { ElMessage } from 'element-plus'

const projects = ref<any[]>([])
const loading = ref(false)
const showDialog = ref(false)
const form = reactive({
  name: '',
  description: '',
})

async function loadProjects() {
  loading.value = true
  try {
    const res = await projectApi.list()
    projects.value = res.data || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.name = ''
  form.description = ''
  showDialog.value = true
}

async function createProject() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入项目名称')
    return
  }
  try {
    await projectApi.create({
      name: form.name.trim(),
      description: form.description.trim() || undefined,
    })
    ElMessage.success('项目创建成功')
    showDialog.value = false
    await loadProjects()
  } catch {
    /* handled by interceptor */
  }
}

async function removeProject(projectId: number) {
  try {
    await projectApi.delete(projectId)
    ElMessage.success('项目已删除')
    await loadProjects()
  } catch {
    /* handled by interceptor */
  }
}

onMounted(loadProjects)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
