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
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { getOverviewApi, getTrendApi, getEmployeeRankingApi } from '@/api/statistics'
import { getOrderListApi } from '@/api/order'
import { ShoppingCart, Wallet, User, UserFilled } from '@element-plus/icons-vue'

const overviewData = ref({})
const recentOrders = ref([])
const employeeRanking = ref([])

const orderChartRef = ref(null)
const revenueChartRef = ref(null)
let orderChart = null
let revenueChart = null

const getStatusType = (status) => {
  const map = {
    'pending_payment': 'warning',
    'pending_assign': 'info',
    'in_progress': 'primary',
    'completed': 'success',
    'canceled': 'danger',
    'refunded': 'danger'
  }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = {
    'pending_payment': '待支付',
    'pending_assign': '待分配',
    'in_progress': '进行中',
    'completed': '已完成',
    'canceled': '已取消',
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
    const [overviewRes, ordersRes, rankingRes] = await Promise.all([
      getOverviewApi(),
      getOrderListApi({ page_size: 5 }),
      getEmployeeRankingApi({ page_size: 5 })
    ])
    overviewData.value = overviewRes.data
    recentOrders.value = ordersRes.data.results || []
    employeeRanking.value = rankingRes.data.results || []
  } catch (error) {
    console.error('获取数据失败', error)
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
</style>
