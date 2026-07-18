<template>
  <div class="finance-page">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="财务概览" name="overview">
        <div class="stats-grid">
          <el-card class="stat-item">
            <div class="stat-header">今日收入</div>
            <div class="stat-value">¥{{ overviewData.todayIncome || 0 }}</div>
          </el-card>
          <el-card class="stat-item">
            <div class="stat-header">今日支出</div>
            <div class="stat-value expense">¥{{ overviewData.todayExpense || 0 }}</div>
          </el-card>
          <el-card class="stat-item">
            <div class="stat-header">本月收入</div>
            <div class="stat-value">¥{{ overviewData.monthIncome || 0 }}</div>
          </el-card>
          <el-card class="stat-item">
            <div class="stat-header">本月支出</div>
            <div class="stat-value expense">¥{{ overviewData.monthExpense || 0 }}</div>
          </el-card>
          <el-card class="stat-item">
            <div class="stat-header">店铺余额</div>
            <div class="stat-value">¥{{ overviewData.balance || 0 }}</div>
          </el-card>
          <el-card class="stat-item">
            <div class="stat-header">待结算金额</div>
            <div class="stat-value warning">¥{{ overviewData.pendingSettlement || 0 }}</div>
          </el-card>
        </div>
      </el-tab-pane>
      <el-tab-pane label="财务流水" name="transactions">
        <div class="search-bar">
          <el-select v-model="searchForm.type" placeholder="类型" clearable style="width: 120px">
            <el-option label="收入" value="income" />
            <el-option label="支出" value="expense" />
          </el-select>
          <el-date-picker v-model="searchForm.date" type="date" placeholder="选择日期" />
          <el-button type="primary" @click="loadTransactions">搜索</el-button>
        </div>
        <el-table :data="transactions" border style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="type" label="类型" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.type === 'income' ? 'success' : 'danger'">
                {{ scope.row.type === 'income' ? '收入' : '支出' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="amount" label="金额" width="120">
            <template #default="scope">
              <span :class="scope.row.type === 'income' ? 'income' : 'expense'">
                {{ scope.row.type === 'income' ? '+' : '-' }}¥{{ scope.row.amount }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" />
          <el-table-column prop="created_at" label="时间" />
        </el-table>
        <el-pagination :total="transactionTotal" :page-size="pageSize" :current-page="page" layout="total, prev, pager, next, jumper" @current-change="handlePageChange" style="margin-top: 20px; text-align: right" />
      </el-tab-pane>
      <el-tab-pane label="工资单" name="salaries">
        <el-table :data="salaries" border style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="employee_name" label="陪玩师" />
          <el-table-column prop="base_salary" label="基本工资" width="120">
            <template #default="scope">¥{{ scope.row.base_salary }}</template>
          </el-table-column>
          <el-table-column prop="commission" label="提成" width="100">
            <template #default="scope">¥{{ scope.row.commission }}</template>
          </el-table-column>
          <el-table-column prop="total" label="总计" width="100">
            <template #default="scope">¥{{ scope.row.total }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.status === 'paid' ? 'success' : 'warning'">
                {{ scope.row.status === 'paid' ? '已发放' : '待发放' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="month" label="月份" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="提现记录" name="withdrawals">
        <el-table :data="withdrawals" border style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="employee_name" label="陪玩师" />
          <el-table-column prop="amount" label="金额" width="100">
            <template #default="scope">¥{{ scope.row.amount }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
              <el-tag :type="getStatusType(scope.row.status)">{{ getStatusText(scope.row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="申请时间" />
          <el-table-column label="操作" width="150">
            <template #default="scope">
              <el-button v-if="scope.row.status === 'pending'" type="success" size="small" @click="handleApprove(scope.row)">通过</el-button>
              <el-button v-if="scope.row.status === 'pending'" type="danger" size="small" @click="handleReject(scope.row)">拒绝</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getFinancialOverviewApi, getTransactionListApi, getSalaryListApi, getWithdrawListApi, approveWithdrawApi, rejectWithdrawApi } from '@/api/finance'

const activeTab = ref('overview')
const overviewData = ref({})
const transactions = ref([])
const salaries = ref([])
const withdrawals = ref([])
const transactionTotal = ref(0)
const page = ref(1)
const pageSize = ref(10)

const searchForm = reactive({ type: '', date: '' })

const getStatusType = (status) => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger', completed: 'primary' }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = { pending: '待审核', approved: '已通过', rejected: '已拒绝', completed: '已完成' }
  return map[status] || status
}

const loadOverview = async () => {
  try { const res = await getFinancialOverviewApi(); overviewData.value = res.data }
  catch (error) { console.error('获取财务概览失败', error) }
}

const loadTransactions = async () => {
  try {
    const res = await getTransactionListApi({ page: page.value, page_size: pageSize.value, ...searchForm })
    transactions.value = res.data.results || []
    transactionTotal.value = res.data.count || 0
  } catch (error) { console.error('获取流水失败', error) }
}

const loadSalaries = async () => {
  try { const res = await getSalaryListApi({ page_size: 50 }); salaries.value = res.data.results || [] }
  catch (error) { console.error('获取工资单失败', error) }
}

const loadWithdrawals = async () => {
  try { const res = await getWithdrawListApi({ page_size: 50 }); withdrawals.value = res.data.results || [] }
  catch (error) { console.error('获取提现记录失败', error) }
}

const handleApprove = async (row) => {
  try { await approveWithdrawApi(row.id); ElMessage.success('审核通过'); loadWithdrawals() }
  catch (error) { ElMessage.error('操作失败') }
}

const handleReject = async (row) => {
  try { await rejectWithdrawApi(row.id); ElMessage.success('已拒绝'); loadWithdrawals() }
  catch (error) { ElMessage.error('操作失败') }
}

const handlePageChange = (val) => { page.value = val; loadTransactions() }
onMounted(() => { loadOverview(); loadTransactions(); loadSalaries(); loadWithdrawals() })
</script>

<style scoped>
.finance-page { padding: 20px; }
.stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.stat-item { text-align: center; }
.stat-header { color: #909399; margin-bottom: 10px; }
.stat-value { font-size: 28px; font-weight: bold; color: #303133; }
.stat-value.expense { color: #f56c6c; }
.stat-value.warning { color: #e6a23c; }
.search-bar { display: flex; gap: 12px; margin-bottom: 20px; }
.income { color: #67c23a; font-weight: bold; }
.expense { color: #f56c6c; font-weight: bold; }
</style>
