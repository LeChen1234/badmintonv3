<template>
  <el-container class="layout-container">
    <el-aside :width="isCollapsed ? '64px' : '220px'" class="layout-aside" :class="{ 'is-collapsed': isCollapsed }">
      <div class="logo">
        <span v-if="!isCollapsed">羽毛球标注系统</span>
        <el-icon v-else :size="20"><DataAnalysis /></el-icon>
      </div>
      <el-menu 
        :default-active="route.path" 
        router 
        class="aside-menu" 
        background-color="#001529"
        text-color="#ffffffa6" 
        active-text-color="#fff"
        :collapse="isCollapsed"
        :collapse-transition="false"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>总览仪表盘</template>
        </el-menu-item>
        <el-menu-item index="/users" v-if="isAdmin">
          <el-icon><User /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>
        <el-menu-item index="/projects" v-if="canManageProjects">
          <el-icon><FolderOpened /></el-icon>
          <template #title>项目管理</template>
        </el-menu-item>
        <el-menu-item index="/tasks">
          <el-icon><List /></el-icon>
          <template #title>任务管理</template>
        </el-menu-item>
        <el-menu-item index="/progress">
          <el-icon><TrendCharts /></el-icon>
          <template #title>进度监控</template>
        </el-menu-item>
        <el-menu-item index="/review">
          <el-icon><Finished /></el-icon>
          <template #title>审核流程</template>
        </el-menu-item>
        <el-menu-item index="/export">
          <el-icon><Download /></el-icon>
          <template #title>数据导出</template>
        </el-menu-item>
      </el-menu>
      <div class="collapse-toggle" @click="toggleCollapse">
        <el-icon :size="18">
          <ArrowLeft v-if="!isCollapsed" />
          <ArrowRight v-else />
        </el-icon>
      </div>
    </el-aside>
    <el-container>
      <el-header class="layout-header" :class="{ 'is-collapsed': isCollapsed }">
        <div class="header-right">
          <span class="user-info">{{ authStore.user?.display_name }}（{{ roleLabel }}）</span>
          <el-button text @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>
      <el-main class="layout-main" :class="{ 'is-collapsed': isCollapsed }">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { DataAnalysis, User, List, TrendCharts, Finished, Download, FolderOpened, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

const route = useRoute()
const authStore = useAuthStore()

const isCollapsed = ref(false)
const COLLAPSE_BREAKPOINT = 992

const roleMap: Record<string, string> = {
  admin: '管理员', expert: '专家', leader: '组长', student: '学生',
}
const roleLabel = computed(() => roleMap[authStore.user?.role || ''] || '未知')
const isAdmin = computed(() => authStore.user?.role === 'admin')
const canManageProjects = computed(() => ['admin', 'expert'].includes(authStore.user?.role || ''))

function handleLogout() {
  authStore.logout()
}

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

function checkScreenSize() {
  if (window.innerWidth < COLLAPSE_BREAKPOINT) {
    isCollapsed.value = true
  }
}

onMounted(() => {
  if (!authStore.user) authStore.fetchUser()
  checkScreenSize()
  window.addEventListener('resize', checkScreenSize)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkScreenSize)
})
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
}

.layout-aside {
  position: fixed;
  left: 0;
  top: 0;
  height: 100vh;
  z-index: 100;
  background: #001529;
  overflow-y: auto;
  transition: width 0.3s ease;
}

.layout-aside.is-collapsed {
  width: 64px;
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
  white-space: nowrap;
  overflow: hidden;
}

.aside-menu {
  border-right: none;
}

.aside-menu:not(.el-menu--collapse) {
  width: 220px;
}

.collapse-toggle {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffffa6;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.3s ease;
}

.collapse-toggle:hover {
  background: #ffffff1a;
  color: #fff;
}

.layout-header {
  position: fixed;
  top: 0;
  right: 0;
  left: 220px;
  z-index: 99;
  height: 56px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  padding: 0 24px;
  transition: left 0.3s ease;
}

.layout-header.is-collapsed {
  left: 64px;
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
  margin-left: 220px;
  margin-top: 56px;
  background: #f5f7fa;
  padding: 20px;
  min-height: calc(100vh - 56px);
  transition: margin-left 0.3s ease;
}

.layout-main.is-collapsed {
  margin-left: 64px;
}

@media (max-width: 768px) {
  .layout-header {
    padding: 0 16px;
  }
  
  .layout-main {
    padding: 12px;
  }
}
</style>
