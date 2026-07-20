import { defineStore } from 'pinia'
import { ref } from 'vue'
import { loginApi, getUserInfoApi, getMenusApi } from '@/api/account'
import { flattenMenuTree, getMenuPaths, getFirstMenuPath } from '@/utils/menu'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref({})
  const menus = ref([])

  const login = async (data) => {
    const res = await loginApi(data)
    token.value = res.data.token
    localStorage.setItem('token', token.value)
    return res
  }

  const getUserInfo = async () => {
    const res = await getUserInfoApi()
    userInfo.value = res.data
    return res
  }

  const getMenus = async () => {
    const res = await getMenusApi()
    menus.value = res.data
    return res
  }

  const getFlatMenus = () => flattenMenuTree(menus.value)

  const getAllowedPaths = () => getMenuPaths(menus.value)

  const getDefaultPath = () => getFirstMenuPath(menus.value)

  const logout = () => {
    token.value = ''
    userInfo.value = {}
    menus.value = []
    localStorage.removeItem('token')
  }

  return {
    token,
    userInfo,
    menus,
    login,
    getUserInfo,
    getMenus,
    getFlatMenus,
    getAllowedPaths,
    getDefaultPath,
    logout
  }
})
