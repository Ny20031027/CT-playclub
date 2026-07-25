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

// 客服欢迎语
export const getCsWelcomeApi = () => request.get('/system/cs-welcome/current/')
export const saveCsWelcomeApi = (data) => request.post('/system/cs-welcome/', data)
export const updateCsWelcomeApi = (id, data) => request.put(`/system/cs-welcome/${id}/`, data)

// 客服关键词规则
export const getCsKeywordListApi = (params) => request.get('/system/cs-keywords/', { params })
export const createCsKeywordApi = (data) => request.post('/system/cs-keywords/', data)
export const updateCsKeywordApi = (id, data) => request.put(`/system/cs-keywords/${id}/`, data)
export const deleteCsKeywordApi = (id) => request.delete(`/system/cs-keywords/${id}/`)

// 服务项目
export const getServiceItemListApi = (params) => request.get('/system/service-items/', { params })
export const createServiceItemApi = (data) => request.post('/system/service-items/', data)
export const updateServiceItemApi = (id, data) => request.put(`/system/service-items/${id}/`, data)
export const deleteServiceItemApi = (id) => request.delete(`/system/service-items/${id}/`)
