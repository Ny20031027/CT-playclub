import request from '@/utils/request'

export const getScheduleListApi = (params) => request.get('/schedule/schedules/', { params })
export const createScheduleApi = (data) => request.post('/schedule/schedules/', data)
export const updateScheduleApi = (id, data) => request.put(`/schedule/schedules/${id}/`, data)
export const deleteScheduleApi = (id) => request.delete(`/schedule/schedules/${id}/`)

export const getLeaveListApi = (params) => request.get('/schedule/leaves/', { params })
export const createLeaveApi = (data) => request.post('/schedule/leaves/', data)
export const updateLeaveApi = (id, data) => request.put(`/schedule/leaves/${id}/`, data)
export const deleteLeaveApi = (id) => request.delete(`/schedule/leaves/${id}/`)
export const approveLeaveApi = (id, data) => request.post(`/schedule/leaves/${id}/approve/`, data)

export const getAttendanceListApi = (params) => request.get('/schedule/attendances/', { params })
export const getShiftListApi = (params) => request.get('/schedule/shifts/', { params })
export const createShiftApi = (data) => request.post('/schedule/shifts/', data)
export const updateShiftApi = (id, data) => request.put(`/schedule/shifts/${id}/`, data)
export const deleteShiftApi = (id) => request.delete(`/schedule/shifts/${id}/`)

export const getReservationListApi = (params) => request.get('/schedule/reservations/', { params })
export const createReservationApi = (data) => request.post('/schedule/reservations/', data)
export const updateReservationApi = (id, data) => request.put(`/schedule/reservations/${id}/`, data)
export const deleteReservationApi = (id) => request.delete(`/schedule/reservations/${id}/`)
