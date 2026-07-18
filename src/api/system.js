import request from '@/utils/request'

export const getConfigListApi = (params) => request.get('/system/configs/', { params })
export const createConfigApi = (data) => request.post('/system/configs/', data)
export const updateConfigApi = (id, data) => request.put(`/system/configs/${id}/`, data)
export const deleteConfigApi = (id) => request.delete(`/system/configs/${id}/`)

export const getDictionaryListApi = (params) => request.get('/system/dictionaries/', { params })
export const createDictionaryApi = (data) => request.post('/system/dictionaries/', data)
export const updateDictionaryApi = (id, data) => request.put(`/system/dictionaries/${id}/`, data)
export const deleteDictionaryApi = (id) => request.delete(`/system/dictionaries/${id}/`)

export const getOperationLogApi = (params) => request.get('/system/operation-logs/', { params })
export const getErrorLogApi = (params) => request.get('/system/error-logs/', { params })
