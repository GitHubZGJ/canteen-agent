<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChatDotRound, DataLine, Dish, Document, Files, MagicStick, Tickets, TrendCharts } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const activeMenu = computed(() => route.path)
const title = computed(() => (route.meta.title as string) || '校园食堂智能体')

const MENU = [
  { path: '/dashboard', label: '经营大屏', icon: DataLine },
  { path: '/dishes', label: '菜品分析', icon: Dish },
  { path: '/forecast', label: '预测备餐', icon: TrendCharts },
  { path: '/optimization', label: '菜单优化', icon: MagicStick },
  { path: '/agent', label: '智能助手', icon: ChatDotRound },
  { path: '/suggestions', label: '建议工单', icon: Tickets },
  { path: '/reports', label: '报告中心', icon: Document },
  { path: '/data', label: '数据管理', icon: Files },
]

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside width="200px" style="background: #001529">
      <div style="color: #fff; text-align: center; padding: 18px 0; font-size: 16px; font-weight: 600">
        食堂智能体
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#001529"
        text-color="#a6adb4"
        active-text-color="#ffffff"
      >
        <el-menu-item v-for="item in MENU" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header
        style="display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid #eee"
      >
        <span style="font-size: 16px; font-weight: 600">{{ title }}</span>
        <el-dropdown @command="onLogout">
          <span style="cursor: pointer">
            {{ auth.user?.username }}（{{ auth.user?.role }}）▾
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main style="background: #f5f7fa">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>