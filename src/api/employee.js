import request from '@/utils/request'

export const getEmployeeListApi = (params) => request.get('/employee/employees/', { params })
export const getEmployeeDetailApi = (id) => request.get(`/employee/employees/${id}/`)
export const createEmployeeApi = (data) => request.post('/employee/employees/', data)
export const updateEmployeeApi = (id, data) => request.put(`/employee/employees/${id}/`, data)
export const deleteEmployeeApi = (id) => request.delete(`/employee/employees/${id}/`)

export const getSkillListApi = (params) => request.get('/employee/skills/', { params })
export const createSkillApi = (data) => request.post('/employee/skills/', data)
export const updateSkillApi = (id, data) => request.put(`/employee/skills/${id}/`, data)
export const deleteSkillApi = (id) => request.delete(`/employee/skills/${id}/`)

export const getTagListApi = (params) => request.get('/employee/tags/', { params })
export const createTagApi = (data) => request.post('/employee/tags/', data)
export const updateTagApi = (id, data) => request.put(`/employee/tags/${id}/`, data)
export const deleteTagApi = (id) => request.delete(`/employee/tags/${id}/`)

export const getWalletListApi = (params) => request.get('/employee/wallets/', { params })
export const getContractListApi = (params) => request.get('/employee/contracts/', { params })
