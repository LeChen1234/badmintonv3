<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="layout-aside">
      <div class="logo">
        <span>羽毛球标注系统</span>
      </div>
      <el-menu :default-active="route.path" router class="aside-menu" background-color="#001529"
        text-color="#ffffffa6" active-text-color="#fff">
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>总览仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/users" v-if="isAdmin">
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
        <el-menu-item index="/progress">
          <el-icon><TrendCharts /></el-icon>
          <span>进度监控</span>
        </el-menu-item>
        <el-menu-item index="/review">
          <el-icon><Finished /></el-icon>
          <span>审核流程</span>
        </el-menu-item>
        <el-menu-item index="/export">
          <el-icon><Download /></el-icon>
          <span>数据导出</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="layout-header">
        <div class="header-right">
          <span class="user-info">{{ authStore.user?.display_name }}（{{ roleLabel }}）</span>
          <el-button text @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { DataAnalysis, User, List, TrendCharts, Finished, Download, FolderOpened } from '@element-plus/icons-vue'

const route = useRoute()
const authStore = useAuthStore()

const roleMap: Record<string, string> = {
  admin: '管理员', expert: '专家', leader: '组长', student: '学生',
}
const roleLabel = computed(() => roleMap[authStore.user?.role || ''] || '未知')
const isAdmin = computed(() => authStore.user?.role === 'admin')
const canManageProjects = computed(() => ['admin', 'expert'].includes(authStore.user?.role || ''))

function handleLogout() {
  authStore.logout()
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
}
.aside-menu {
  border-right: none;
}
.layout-header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  padding: 0 24px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.user-info {
  font-size: 14px;
  color: #606266;
}
.layout-main {
  background: #f5f7fa;
  padding: 24px;
}
</style>
