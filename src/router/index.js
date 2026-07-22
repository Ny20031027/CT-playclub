import { createRouter, createWebHashHistory } from 'vue-router'
import { useUserStore } from '@/store/user'
import { getMenuPaths, getFirstMenuPath } from '@/utils/menu'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue')
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/layout/index.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '数据概览', icon: 'el-icon-data-board' }
      },
      {
        path: 'employees',
        name: 'Employees',
        component: () => import('@/views/employee/index.vue'),
        meta: { title: '陪玩师管理', icon: 'el-icon-user' }
      },
      {
        path: 'customers',
        name: 'Customers',
        component: () => import('@/views/customer/index.vue'),
        meta: { title: '客户管理', icon: 'el-icon-customers' }
      },
      {
        path: 'orders',
        name: 'Orders',
        component: () => import('@/views/order/index.vue'),
        meta: { title: '订单管理', icon: 'el-icon-s-order' }
      },
      {
        path: 'tickets',
        name: 'Tickets',
        component: () => import('@/views/ticket/index.vue'),
        meta: { title: '售后工单', icon: 'el-icon-ticket' }
      },
      {
        path: 'finance',
        name: 'Finance',
        component: () => import('@/views/finance/index.vue'),
        meta: { title: '财务管理', icon: 'el-icon-money' }
      },
      {
        path: 'schedule',
        name: 'Schedule',
        component: () => import('@/views/schedule/index.vue'),
        meta: { title: '排班管理', icon: 'el-icon-date' }
      },
      {
        path: 'statistics',
        name: 'Statistics',
        component: () => import('@/views/statistics/index.vue'),
        meta: { title: '数据统计', icon: 'el-icon-pie-chart' }
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/system/index.vue'),
        meta: { title: '系统设置', icon: 'el-icon-setting' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  if (to.path === '/login') {
    next()
    return
  }

  if (!userStore.token) {
    next('/login')
    return
  }

  if (!userStore.userInfo.id) {
    try {
      await userStore.getUserInfo()
    } catch (error) {
      userStore.logout()
      next('/login')
      return
    }
  }

  if (!userStore.menus.length) {
    try {
      await userStore.getMenus()
    } catch (error) {
      userStore.logout()
      next('/login')
      return
    }
  }

  if (userStore.userInfo.is_superuser) {
    next()
    return
  }

  const allowedPaths = getMenuPaths(userStore.menus)
  const currentPath = to.path === '/' ? '/dashboard' : to.path

  if (!allowedPaths.length) {
    next('/login')
    return
  }

  if (!allowedPaths.includes(currentPath)) {
    next(getFirstMenuPath(userStore.menus))
    return
  }

  next()
})

export default router
