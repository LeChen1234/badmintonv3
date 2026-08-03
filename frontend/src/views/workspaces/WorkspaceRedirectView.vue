<template>
  <div class="workspace-loading" v-loading="true">正在进入工作台…</div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { WORKSPACE_PATHS } from '@/constants/workspaces'

const router = useRouter()
const authStore = useAuthStore()

onMounted(async () => {
  if (!authStore.user) await authStore.fetchUser()
  router.replace(WORKSPACE_PATHS[authStore.workspaceRole])
})
</script>

<style scoped>.workspace-loading { min-height: 240px; display: grid; place-items: center; color: #909399; }</style>
