<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <div class="header-actions">
            <el-button type="danger" :disabled="selectedIds.length === 0" @click="batchDisable">批量禁用</el-button>
            <el-button type="success" :disabled="selectedIds.length === 0" @click="batchEnable">批量启用</el-button>
            <el-button type="primary" @click="showCreateDialog = true">新建用户</el-button>
          </div>
        </div>
      </template>
      <el-table :data="users" stripe v-loading="loading" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="display_name" label="显示名" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)">{{ roleLabel(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="editUser(row)">编辑</el-button>
            <el-popconfirm v-if="row.role.toUpperCase() !== 'ADMIN'" :title="row.is_active ? '确定禁用此用户？' : '确定启用此用户？'" @confirm="toggleUserStatus(row)">
              <template #reference>
                <el-button size="small" :type="row.is_active ? 'danger' : 'success'">
                  {{ row.is_active ? '禁用' : '启用' }}
                </el-button>
              </template>
            </el-popconfirm>
            <el-tooltip v-else content="管理员账号不可禁用" placement="top">
              <el-button size="small" disabled>禁用</el-button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showCreateDialog" :title="editingUser ? '编辑用户' : '新建用户'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="!!editingUser" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" :placeholder="editingUser ? '留空则不修改' : '请输入密码'" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role">
            <el-option label="管理员" value="admin" />
            <el-option label="标注专家" value="expert" />
            <el-option label="标注组长" value="leader" />
            <el-option label="学生标注员" value="student" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { userApi } from '@/api'
import { ElMessage } from 'element-plus'

const users = ref<any[]>([])
const loading = ref(false)
const showCreateDialog = ref(false)
const editingUser = ref<any>(null)
const form = reactive({ username: '', display_name: '', password: '', role: 'student' })
const selectedIds = ref<number[]>([])

const roleMap: Record<string, string> = { ADMIN: '管理员', admin: '管理员', EXPERT: '专家', expert: '专家', LEADER: '组长', leader: '组长', STUDENT: '学生', student: '学生' }
const roleLabel = (r: string) => roleMap[r] || roleMap[r?.toLowerCase()] || r
const roleTagType = (r: string) => ({ ADMIN: 'danger', admin: 'danger', EXPERT: 'warning', expert: 'warning', LEADER: '', leader: '', STUDENT: 'info', student: 'info' }[r] || '')

async function loadUsers() {
  loading.value = true
  try {
    const res = await userApi.list()
    users.value = res.data
  } finally {
    loading.value = false
  }
}

function handleSelectionChange(selection: any[]) {
  selectedIds.value = selection.map(item => item.id)
}

async function batchDisable() {
  const adminIds = users.value.filter(u => u.role.toUpperCase() === 'ADMIN').map(u => u.id)
  const toDisable = selectedIds.value.filter(id => !adminIds.includes(id))
  if (toDisable.length === 0) {
    ElMessage.warning('没有可禁用的用户（管理员账号不可禁用）')
    return
  }
  try {
    await Promise.all(toDisable.map(id => userApi.update(id, { is_active: false })))
    ElMessage.success(`已禁用 ${toDisable.length} 个用户`)
    selectedIds.value = []
    loadUsers()
  } catch { /* handled by interceptor */ }
}

async function batchEnable() {
  try {
    await Promise.all(selectedIds.value.map(id => userApi.update(id, { is_active: true })))
    ElMessage.success(`已启用 ${selectedIds.value.length} 个用户`)
    selectedIds.value = []
    loadUsers()
  } catch { /* handled by interceptor */ }
}

function editUser(user: any) {
  editingUser.value = user
  Object.assign(form, { username: user.username, display_name: user.display_name, password: '', role: user.role })
  showCreateDialog.value = true
}

async function saveUser() {
  try {
    if (editingUser.value) {
      const data: any = { display_name: form.display_name, role: form.role }
      if (form.password) data.password = form.password
      await userApi.update(editingUser.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await userApi.create(form)
      ElMessage.success('创建成功')
    }
    showCreateDialog.value = false
    editingUser.value = null
    loadUsers()
  } catch { /* handled by interceptor */ }
}

async function toggleUserStatus(user: any) {
  try {
    const newStatus = !user.is_active
    await userApi.update(user.id, { is_active: newStatus })
    ElMessage.success(newStatus ? '已启用' : '已禁用')
    loadUsers()
  } catch { /* handled by interceptor */ }
}

onMounted(loadUsers)
</script>

<style scoped>
.page-container {
  background-color: #fff;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
}
</style>
