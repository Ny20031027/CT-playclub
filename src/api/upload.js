import request from '@/utils/request'

export const uploadImageApi = (data) => request.post('/upload/files/image/', data)
export const uploadFileApi = (data) => request.post('/upload/files/', data)
export const getFileListApi = (params) => request.get('/upload/files/', { params })
export const deleteFileApi = (id) => request.delete(`/upload/files/${id}/`)
