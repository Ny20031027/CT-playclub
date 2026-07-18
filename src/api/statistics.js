import request from '@/utils/request'

export const getOverviewApi = () => request.get('/statistics/stats/overview/')
export const getTrendApi = (params) => request.get('/statistics/stats/trend/', { params })
export const getEmployeeRankingApi = (params) => request.get('/statistics/stats/employee-rank/', { params })
export const getOrderStatisticsApi = (params) => request.get('/statistics/stats/order-status/', { params })
export const getFinancialStatisticsApi = (params) => request.get('/statistics/stats/finance-overview/', { params })

export const getDailyReportApi = (params) => request.get('/statistics/daily/', { params })
export const getWeeklyReportApi = (params) => request.get('/statistics/daily/', { params })
export const getMonthlyReportApi = (params) => request.get('/statistics/monthly/', { params })
