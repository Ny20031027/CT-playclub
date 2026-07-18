import request from '@/utils/request'

export const getCustomerListApi = (params) => request.get('/customer/customers/', { params })
export const getCustomerDetailApi = (id) => request.get(`/customer/customers/${id}/`)
export const createCustomerApi = (data) => request.post('/customer/customers/', data)
export const updateCustomerApi = (id, data) => request.put(`/customer/customers/${id}/`, data)
export const deleteCustomerApi = (id) => request.delete(`/customer/customers/${id}/`)

export const getLevelListApi = (params) => request.get('/customer/levels/', { params })
export const createLevelApi = (data) => request.post('/customer/levels/', data)
export const updateLevelApi = (id, data) => request.put(`/customer/levels/${id}/`, data)
export const deleteLevelApi = (id) => request.delete(`/customer/levels/${id}/`)

export const getTagListApi = (params) => request.get('/customer/tags/', { params })
export const createTagApi = (data) => request.post('/customer/tags/', data)
export const updateTagApi = (id, data) => request.put(`/customer/tags/${id}/`, data)
export const deleteTagApi = (id) => request.delete(`/customer/tags/${id}/`)

export const getBlacklistApi = (params) => request.get('/customer/blacklist/', { params })
export const addBlacklistApi = (data) => request.post('/customer/blacklist/', data)
export const removeBlacklistApi = (id) => request.delete(`/customer/blacklist/${id}/`)

export const getConsumptionRecordsApi = (params) => request.get('/customer/consumption-records/', { params })
