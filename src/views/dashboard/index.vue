<template>
  <div class="dashboard">
    <div class="stats-row">
      <el-card class="stat-card">
        <div class="stat-icon order-icon"><el-icon><ShoppingCart /></el-icon></div>
        <div class="stat-info">
          <div class="stat-value">{{ overviewData.totalOrders || 0 }}</div>
          <div class="stat-label">今日订单</div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-icon revenue-icon"><el-icon><Wallet /></el-icon></div>
        <div class="stat-info">
          <div class="stat-value">¥{{ overviewData.totalRevenue || 0 }}</div>
          <div class="stat-label">今日营收</div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-icon employee-icon"><el-icon><User /></el-icon></div>
        <div class="stat-info">
          <div class="stat-value">{{ overviewData.onlineEmployees || 0 }}</div>
          <div class="stat-label">在线陪玩师</div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-icon customer-icon"><el-icon><UserFilled /></el-icon></div>
        <div class="stat-info">
          <div class="stat-value">{{ overviewData.newCustomers || 0 }}</div>
          <div class="stat-label">新增客户</div>
        </div>
      </el-card>
    </div>
    <div class="charts-row">
      <el-card class="chart-card">
        <template #header>订单趋势</template>
        <div ref="orderChartRef" class="chart"></div>
      </el-card>
      <el-card class="chart-card">
        <template #header>营收分布</template>
        <div ref="revenueChartRef" class="chart"></div>
      </el-card>
    </div>
    <div class="bottom-row">
      <el-card class="list-card">
        <template #header>最近订单</template>
        <el-table :data="recentOrders" border style="width: 100%">
          <el-table-column prop="order_no" label="订单号" />
          <el-table-column prop="customer_name" label="客户" />
          <el-table-column prop="employee_name" label="陪玩师" />
          <el-table-column prop="amount" label="金额">
            <template #default="scope">¥{{ scope.row.amount }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态">
            <template #default="scope">
              <el-tag :type="getStatusType(scope.row.status)">{{ getStatusText(scope.row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" />
        </el-table>
      </el-card>
      <el-card class="list-card">
        <template #header>陪玩师排行</template>
        <el-table :data="employeeRanking" border style="width: 100%">
          <el-table-column prop="rank" label="排名" width="60">
            <template #default="scope">
              <el-tag v-if="scope.row.rank === 1" type="danger">1</el-tag>
              <el-tag v-else-if="scope.row.rank === 2" type="warning">2</el-tag>
              <el-tag v-else-if="scope.row.rank === 3" type="success">3</el-tag>
              <span v-else>{{ scope.row.rank }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="陪玩师" />
          <el-table-column prop="order_count" label="接单量" />
          <el-table-column prop="revenue" label="营收">
            <template #default="scope">¥{{ scope.row.revenue }}</template>
          </el-table-column>
          <el-table-column prop="rating" label="评分" />
        </el-table>
      </el-card>
      <el-card class="list-card">
        <template #header>
          <div class="card-header">
            <span>本月打手下单榜</span>
            <span class="header-sub">按老板下单数排序</span>
          </div>
        </template>
        <el-table :data="monthlyDasherRanking" border style="width: 100%">
          <el-table-column prop="rank" label="排名" width="60">
            <template #default="scope">
              <el-tag v-if="scope.row.rank === 1" type="danger">1</el-tag>
              <el-tag v-else-if="scope.row.rank === 2" type="warning">2</el-tag>
              <el-tag v-else-if="scope.row.rank === 3" type="success">3</el-tag>
              <span v-else>{{ scope.row.rank }}</span>
            </template>
          </el-table-column>
          <el-table-column label="打手" min-width="140">
            <template #default="scope">
              <div class="employee-cell">
                <el-avatar :size="32" :src="scope.row.employee_avatar" />
                <span>{{ scope.row.employee_name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="order_count" label="本月下单" width="100">
            <template #default="scope">{{ scope.row.order_count }} 单</template>
          </el-table-column>
          <el-table-column prop="total_amount" label="订单金额" width="110">
            <template #default="scope">¥{{ scope.row.total_amount }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="scope">
              <el-button type="primary" link @click="openDasherDetail(scope.row)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-dialog v-model="detailVisible" title="本月下单详情" width="860px">
      <el-descriptions :column="3" border class="detail-summary">
        <el-descriptions-item label="打手">{{ currentDasherDetail.employee_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="月份">{{ currentDasherDetail.month || '-' }}</el-descriptions-item>
        <el-descriptions-item label="订单数">{{ currentDasherDetail.order_count || 0 }} 单</el-descriptions-item>
      </el-descriptions>
      <el-table v-loading="detailLoading" :data="currentDasherDetail.orders || []" border style="width: 100%">
        <el-table-column prop="order_no" label="订单号" min-width="170" />
        <el-table-column prop="customer_name" label="老板" width="120" />
        <el-table-column prop="game_name" label="游戏" width="120" />
        <el-table-column prop="status_text" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status_text || getStatusText(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="pay_amount" label="金额" width="100">
          <template #default="scope">¥{{ scope.row.pay_amount }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="下单时间" min-width="160" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import {
  getOverviewApi,
  getTrendApi,
  getEmployeeRankingApi,
  getMonthlyDasherOrderRankApi,
  getMonthlyDasherOrderDetailApi
} from '@/api/statistics'
import { getOrderListApi } from '@/api/order'
import { ShoppingCart, Wallet, User, UserFilled } from '@element-plus/icons-vue'

const overviewData = ref({})
const recentOrders = ref([])
const employeeRanking = ref([])
const monthlyDasherRanking = ref([])
const detailVisible = ref(false)
const detailLoading = ref(false)
const currentDasherDetail = ref({})

const orderChartRef = ref(null)
const revenueChartRef = ref(null)
let orderChart = null
let revenueChart = null

const getStatusType = (status) => {
  const map = {
    'pending_payment': 'warning',
    'pending_assign': 'info',
    'published': 'info',
    'claimed': 'primary',
    'confirming': 'warning',
    'in_progress': 'primary',
    'completed': 'success',
    'reviewed': 'success',
    'canceled': 'danger',
    'cancelled': 'danger',
    'refunded': 'danger'
  }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = {
    'pending_payment': '待支付',
    'pending_assign': '待分配',
    'published': '可领取',
    'claimed': '待开始',
    'confirming': '待客户确认',
    'in_progress': '进行中',
    'completed': '已完成',
    'reviewed': '已评价',
    'canceled': '已取消',
    'cancelled': '已取消',
    'refunded': '已退款'
  }
  return map[status] || status
}

const initCharts = () => {
  orderChart = echarts.init(orderChartRef.value)
  revenueChart = echarts.init(revenueChartRef.value)

  orderChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] },
    yAxis: { type: 'value' },
    series: [{
      data: [120, 200, 150, 80, 220, 180],
      type: 'line',
      smooth: true,
      areaStyle: {}
    }]
  })

  revenueChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      data: [
        { value: 40, name: '王者荣耀' },
        { value: 30, name: '英雄联盟' },
        { value: 20, name: '和平精英' },
        { value: 10, name: '其他' }
      ],
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
      label: { show: false }
    }]
  })
}

const fetchData = async () => {
  try {
    const [overviewRes, ordersRes, rankingRes, monthlyRankRes] = await Promise.all([
      getOverviewApi(),
      getOrderListApi({ page_size: 5 }),
      getEmployeeRankingApi({ limit: 5 }),
      getMonthlyDasherOrderRankApi({ limit: 5 })
    ])
    const overview = overviewRes.data || {}
    overviewData.value = {
      ...overview,
      totalOrders: overview.totalOrders ?? overview.today_orders ?? 0,
      totalRevenue: overview.totalRevenue ?? overview.today_amount ?? 0,
      onlineEmployees: overview.onlineEmployees ?? overview.active_employees ?? 0,
      newCustomers: overview.newCustomers ?? overview.total_customers ?? 0
    }
    recentOrders.value = (ordersRes.data.results || []).map((order) => ({
      ...order,
      employee_name: order.employee_name || order.assigned_employee_name || (order.members && order.members[0] && order.members[0].employee_name) || '-',
      amount: order.amount ?? order.pay_amount ?? 0
    }))
    employeeRanking.value = (rankingRes.data.results || rankingRes.data || []).map((employee) => ({
      ...employee,
      name: employee.name || employee.employee_name,
      revenue: employee.revenue ?? employee.total_amount ?? 0,
      rating: employee.rating ?? employee.avg_rating ?? '-'
    }))
    monthlyDasherRanking.value = monthlyRankRes.data.results || []
  } catch (error) {
    console.error('获取数据失败', error)
  }
}

const openDasherDetail = async (row) => {
  detailVisible.value = true
  detailLoading.value = true
  currentDasherDetail.value = {
    employee_id: row.employee_id,
    employee_name: row.employee_name,
    order_count: row.order_count,
    orders: []
  }
  try {
    const res = await getMonthlyDasherOrderDetailApi({ employee_id: row.employee_id })
    currentDasherDetail.value = res.data || currentDasherDetail.value
  } catch (error) {
    console.error('获取打手订单详情失败', error)
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  initCharts()
  fetchData()
})

onUnmounted(() => {
  orderChart?.dispose()
  revenueChart?.dispose()
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 20px;
}

.stat-icon {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
}

.order-icon { background-color: #e6f7ff; color: #1890ff; }
.revenue-icon { background-color: #f6ffed; color: #52c41a; }
.employee-icon { background-color: #fff7e6; color: #fa8c16; }
.customer-icon { background-color: #f9f0ff; color: #722ed1; }

.stat-value { font-size: 28px; font-weight: bold; color: #303133; }
.stat-label { font-size: 14px; color: #909399; margin-top: 4px; }

.charts-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.chart-card { height: 350px; }
.chart { width: 100%; height: calc(100% - 50px); }

.bottom-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.list-card { height: 400px; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-sub {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.employee-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.employee-cell span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-summary {
  margin-bottom: 16px;
}
</style>
