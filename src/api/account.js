import request from '@/utils/request'

export const loginApi = (data) => request.post('/account/auth/login/', data)
export const logoutApi = () => request.post('/account/auth/logout/')
export const getUserInfoApi = () => request.get('/account/users/info/')
export const getMenusApi = () => request.get('/account/users/menus/')
export const getPermissionsApi = () => request.get('/account/users/permissions/')
export const getUserListApi = (params) => request.get('/account/users/', { params })
export const createUserApi = (data) => request.post('/account/users/', data)
export const updateUserApi = (id, data) => request.put(`/account/users/${id}/`, data)
export const deleteUserApi = (id) => request.delete(`/account/users/${id}/`)

export const getRoleListApi = (params) => request.get('/account/roles/', { params })
export const createRoleApi = (data) => request.post('/account/roles/', data)
export const updateRoleApi = (id, data) => request.put(`/account/roles/${id}/`, data)
export const deleteRoleApi = (id) => request.delete(`/account/roles/${id}/`)

export const getDepartmentListApi = (params) => request.get('/account/departments/', { params })
export const createDepartmentApi = (data) => request.post('/account/departments/', data)
export const updateDepartmentApi = (id, data) => request.put(`/account/departments/${id}/`, data)
export const deleteDepartmentApi = (id) => request.delete(`/account/departments/${id}/`)
