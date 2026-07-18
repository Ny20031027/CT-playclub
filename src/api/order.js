import request from '@/utils/request'

export const getOrderListApi = (params) => request.get('/order/orders/', { params })
export const getOrderDetailApi = (id) => request.get(`/order/orders/${id}/`)
export const createOrderApi = (data) => request.post('/order/orders/', data)
export const updateOrderApi = (id, data) => request.put(`/order/orders/${id}/`, data)
export const deleteOrderApi = (id) => request.delete(`/order/orders/${id}/`)

export const assignOrderApi = (id, data) => request.post(`/order/orders/${id}/assign/`, data)
export const completeOrderApi = (id) => request.post(`/order/orders/${id}/complete/`)
export const cancelOrderApi = (id) => request.post(`/order/orders/${id}/cancel/`)
export const refundOrderApi = (id, data) => request.post(`/order/orders/${id}/refund/`, data)

export const getCommentListApi = (params) => request.get('/order/comments/', { params })
export const createCommentApi = (data) => request.post('/order/comments/', data)

export const getStatusListApi = () => request.get('/order/status/')
