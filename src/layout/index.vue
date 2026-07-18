<template>
  <div class="app-container">
    <el-container>
      <el-aside :width="isCollapse ? '64px' : '200px'" class="sidebar">
        <div class="logo">
          <el-icon v-if="isCollapse"><Menu /></el-icon>
          <span v-else>陪玩店管理</span>
        </div>
        <el-menu :default-active="activeMenu" :collapse="isCollapse" mode="vertical" background-color="#2a3038" text-color="#bfcbd9" active-text-color="#409eff" @select="handleMenuSelect">
          <el-menu-item v-for="item in menuList" :key="item.path" :index="item.path">
            <el-icon><component :is="getIcon(item.icon)" /></el-icon>
            <template #title>{{ item.title }}</template>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header class="header">
          <div class="header-left">
            <el-button type="text" @click="isCollapse = !isCollapse">
              <el-icon><Menu /></el-icon>
            </el-button>
            <span class="title">{{ currentTitle }}</span>
          </div>
          <div class="header-right">
            <el-dropdown>
              <span class="user-info">
                <el-icon><User /></el-icon>
                <span>{{ userStore.userInfo.username || '管理员' }}</span>
                <el-icon><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>
        <el-main class="main">
          <router-view />
        </el-main>
        <el-footer class="footer">
          <span>© 2026 陪玩店综合管理平台 PlayClub Management System</span>
        </el-footer>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/store/user'
import { ElMessage } from 'element-plus'
import { 
  Menu, ArrowDown, User,
  DataBoard, User as UserIcon, UserFilled,
  ShoppingCart, Wallet, Calendar, PieChart, Setting
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const isCollapse = ref(false)

const iconMap = {
  'el-icon-data-board': DataBoard,
  'el-icon-user': UserIcon,
  'el-icon-customers': UserFilled,
  'el-icon-s-order': ShoppingCart,
  'el-icon-money': Wallet,
  'el-icon-date': Calendar,
  'el-icon-pie-chart': PieChart,
  'el-icon-setting': Setting
}

const menuList = computed(() => {
  return [
    { path: '/dashboard', title: '数据概览', icon: 'el-icon-data-board' },
    { path: '/employees', title: '陪玩师管理', icon: 'el-icon-user' },
    { path: '/customers', title: '客户管理', icon: 'el-icon-customers' },
    { path: '/orders', title: '订单管理', icon: 'el-icon-s-order' },
    { path: '/finance', title: '财务管理', icon: 'el-icon-money' },
    { path: '/schedule', title: '排班管理', icon: 'el-icon-date' },
    { path: '/statistics', title: '数据统计', icon: 'el-icon-pie-chart' },
    { path: '/system', title: '系统设置', icon: 'el-icon-setting' }
  ]
})

const activeMenu = computed(() => route.path)

const currentTitle = computed(() => {
  const menu = menuList.value.find(m => m.path === route.path)
  return menu ? menu.title : ''
})

const getIcon = (iconName) => {
  return iconMap[iconName] || DataBoard
}

const handleMenuSelect = (index) => {
  router.push(index)
}

const handleLogout = () => {
  userStore.logout()
  ElMessage.success('退出成功')
  router.push('/login')
}

onMounted(async () => {
  if (!userStore.userInfo.id) {
    await userStore.getUserInfo()
  }
})
</script>

<style scoped>
.app-container {
  height: 100vh;
}

.sidebar {
  background-color: #2a3038;
  transition: width 0.3s;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  border-bottom: 1px solid #3a4149;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #606266;
  cursor: pointer;
}

.main {
  padding: 20px;
  background-color: #f5f7fa;
}

.footer {
  text-align: center;
  padding: 12px;
  background-color: #fff;
  border-top: 1px solid #e6e6e6;
  color: #909399;
  font-size: 12px;
}
</style>
