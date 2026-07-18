import request from '@/utils/request'

export const getWalletListApi = (params) => request.get('/finance/wallets/', { params })
export const getTransactionListApi = (params) => request.get('/finance/transactions/', { params })
export const getSettlementListApi = (params) => request.get('/finance/settlements/', { params })
export const getSalaryListApi = (params) => request.get('/finance/salaries/', { params })
export const getWithdrawListApi = (params) => request.get('/finance/withdraws/', { params })

export const createWithdrawApi = (data) => request.post('/finance/withdraws/', data)
export const approveWithdrawApi = (id, data) => request.post(`/finance/withdraws/${id}/approve/`, data)
export const rejectWithdrawApi = (id, data) => request.post(`/finance/withdraws/${id}/reject/`, data)

export const getFinancialOverviewApi = () => request.get('/finance/overview/')
