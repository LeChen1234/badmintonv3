<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="layout-aside">
      <div class="logo">
        <span>羽毛球标注系统</span>
        <small>{{ workspaceLabel }}工作台</small>
      </div>
      <el-menu :default-active="route.path" router class="aside-menu" background-color="#001529"
        text-color="#ffffffa6" active-text-color="#fff">
        <el-menu-item :index="currentWorkspacePath">
          <el-icon><House /></el-icon>
          <span>{{ workspaceLabel }}工作台</span>
        </el-menu-item>
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>{{ canAtLeast('leader') ? '总览仪表盘' : '个人总览' }}</span>
        </el-menu-item>
        <el-menu-item index="/users" v-if="canManageUsers">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/projects" v-if="canManageProjects">
          <el-icon><FolderOpened /></el-icon>
          <span>项目管理</span>
        </el-menu-item>
        <el-menu-item index="/tasks">
          <el-icon><List /></el-icon>
          <span>任务管理</span>
        </el-menu-item>
        <el-menu-item index="/progress" v-if="canAtLeast('leader')">
          <el-icon><TrendCharts /></el-icon>
          <span>进度监控</span>
        </el-menu-item>
        <el-menu-item index="/review" v-if="canAtLeast('leader')">
          <el-icon><Finished /></el-icon>
          <span>审核流程</span>
        </el-menu-item>
        <el-menu-item index="/export" v-if="isSuperAdmin">
          <el-icon><Download /></el-icon>
          <span>数据导出</span>
        </el-menu-item>
        <el-menu-item index="/research" v-if="canResearch">
          <el-icon><DataLine /></el-icon>
          <span>主动学习闭环</span>
        </el-menu-item>
        <el-menu-item index="/guide">
          <el-icon><Reading /></el-icon>
          <span>新手使用指南</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="layout-header">
        <div class="workspace-switcher">
          <div class="workspace-switcher-label">
            <span>当前工作台</span>
            <small>只切换界面，不改变真实身份</small>
          </div>
          <el-select
            :model-value="currentWorkspaceRole"
            class="workspace-select"
            @change="handleWorkspaceChange"
          >
            <el-option
              v-for="item in workspaceOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleUserMenuCommand">
            <span class="user-info el-dropdown-link">
              {{ authStore.user?.display_name }}（{{ roleLabel }}）
              <el-icon class="el-icon--right">
                <arrow-down />
              </el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="changePassword">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>

    <!-- 修改密码对话框 -->
    <el-dialog title="修改密码" v-model="changePasswordDialogVisible" width="400px" @close="resetPasswordForm">
      <el-form :model="passwordForm" ref="passwordFormRef" :rules="passwordRules" label-width="100px"
        @submit.prevent="submitChangePassword">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password placeholder="请输入原密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="请再次输入密码"
            @keyup.enter="submitChangePassword" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="changePasswordDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitChangePassword" :loading="changePasswordLoading">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api'
import { DataAnalysis, User, List, TrendCharts, Finished, Download, FolderOpened, ArrowDown, DataLine, Reading, House } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import {
  WORKSPACE_LABELS,
  WORKSPACE_PATHS,
  workspaceAtLeast,
  type WorkspaceRole,
} from '@/constants/workspaces'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const passwordFormRef = ref<FormInstance>()
const changePasswordDialogVisible = ref(false)
const changePasswordLoading = ref(false)

const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const passwordRules = {
  old_password: [
    { required: true, message: '请输入原密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
}

const roleMap: Record<string, string> = {
  super_admin: '超级管理员', admin: '管理员', expert: '专家', leader: '组长', student: '学生',
}
const roleLabel = computed(() => roleMap[authStore.user?.role || ''] || '未知')
const currentWorkspaceRole = computed(() => authStore.workspaceRole)
const workspaceLabel = computed(() => WORKSPACE_LABELS[currentWorkspaceRole.value])
const currentWorkspacePath = computed(() => WORKSPACE_PATHS[currentWorkspaceRole.value])
const workspaceOptions = computed(() => authStore.availableWorkspaceRoles.map((workspaceRole) => ({
  value: workspaceRole,
  label: `${WORKSPACE_LABELS[workspaceRole]}工作台`,
})))
const isSuperAdmin = computed(() => authStore.user?.role === 'super_admin' && currentWorkspaceRole.value === 'super_admin')
const canManageUsers = computed(() =>
  workspaceAtLeast(currentWorkspaceRole.value, 'admin')
  && ['super_admin', 'admin'].includes(authStore.user?.role || ''),
)
const canManageProjects = computed(() =>
  workspaceAtLeast(currentWorkspaceRole.value, 'expert')
  && ['super_admin', 'admin', 'expert'].includes(authStore.user?.role || ''),
)
const canResearch = computed(() =>
  workspaceAtLeast(currentWorkspaceRole.value, 'leader')
  && ['super_admin', 'admin', 'expert', 'leader'].includes(authStore.user?.role || ''),
)

function canAtLeast(required: WorkspaceRole) {
  return workspaceAtLeast(currentWorkspaceRole.value, required)
}

function handleWorkspaceChange(value: WorkspaceRole) {
  if (!authStore.setWorkspaceRole(value)) {
    ElMessage.warning('当前账号不能进入该工作台')
    return
  }
  router.push(WORKSPACE_PATHS[value])
}

function handleUserMenuCommand(command: string) {
  if (command === 'logout') {
    handleLogout()
  } else if (command === 'changePassword') {
    changePasswordDialogVisible.value = true
  }
}

function handleLogout() {
  authStore.logout()
}

async function submitChangePassword() {
  if (!passwordFormRef.value) return

  await passwordFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
      ElMessage.error('新密码和确认密码不一致')
      return
    }

    changePasswordLoading.value = true
    try {
      await authApi.changePassword({
        old_password: passwordForm.value.old_password,
        new_password: passwordForm.value.new_password,
        confirm_password: passwordForm.value.confirm_password,
      })
      ElMessage.success('密码修改成功！')
      changePasswordDialogVisible.value = false
      resetPasswordForm()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.detail || '修改密码失败')
    } finally {
      changePasswordLoading.value = false
    }
  })
}

function resetPasswordForm() {
  passwordForm.value = {
    old_password: '',
    new_password: '',
    confirm_password: '',
  }
  passwordFormRef.value?.clearValidate()
}

onMounted(() => {
  if (!authStore.user) authStore.fetchUser()
})
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
}
.layout-aside {
  background: #001529;
  overflow-y: auto;
}
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid #ffffff1a;
  flex-direction: column;
  gap: 2px;
}
.logo small {
  color: #ffffff73;
  font-size: 11px;
  font-weight: 400;
}
.aside-menu {
  border-right: none;
}
.layout-header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  padding: 0 24px;
}
.workspace-switcher {
  display: flex;
  align-items: center;
  gap: 12px;
}
.workspace-switcher-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: #303133;
  font-size: 13px;
}
.workspace-switcher-label small {
  color: #909399;
  font-size: 11px;
}
.workspace-select {
  width: 180px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.user-info {
  font-size: 14px;
  color: #606266;
  cursor: pointer;
  display: flex;
  align-items: center;
}
.el-dropdown-link {
  display: flex;
  align-items: center;
  gap: 4px;
}
.layout-main {
  background: #f5f7fa;
  padding: 24px;
}
</style>
