import request from '@/utils/request'

export const getTicketListApi = (params) => request.get('/order/tickets/', { params })
export const getTicketDetailApi = (id) => request.get(`/order/tickets/${id}/`)
export const closeTicketApi = (id, data) => request.post(`/order/tickets/${id}/close/`, data)
