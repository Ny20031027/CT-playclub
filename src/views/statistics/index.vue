<template>
  <div class="statistics-page">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="订单统计" name="orders">
        <div class="chart-section">
          <el-card>
            <template #header>订单数量趋势</template>
            <div ref="orderTrendChart" class="chart"></div>
          </el-card>
          <el-card>
            <template #header>订单状态分布</template>
            <div ref="orderStatusChart" class="chart"></div>
          </el-card>
        </div>
      </el-tab-pane>
      <el-tab-pane label="财务统计" name="finance">
        <div class="chart-section">
          <el-card>
            <template #header>营收趋势</template>
            <div ref="revenueTrendChart" class="chart"></div>
          </el-card>
          <el-card>
            <template #header>收入构成</template>
            <div ref="revenuePieChart" class="chart"></div>
          </el-card>
        </div>
      </el-tab-pane>
      <el-tab-pane label="陪玩师排行" name="ranking">
        <el-table :data="rankingData" border style="width: 100%">
          <el-table-column prop="rank" label="排名" width="80">
            <template #default="scope">
              <el-tag v-if="scope.row.rank === 1" type="danger" size="large">🥇</el-tag>
              <el-tag v-else-if="scope.row.rank === 2" type="warning" size="large">🥈</el-tag>
              <el-tag v-else-if="scope.row.rank === 3" type="success" size="large">🥉</el-tag>
              <span v-else>{{ scope.row.rank }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="陪玩师" />
          <el-table-column prop="order_count" label="接单量" />
          <el-table-column prop="revenue" label="营收">
            <template #default="scope">¥{{ scope.row.revenue }}</template>
          </el-table-column>
          <el-table-column prop="rating" label="评分" />
          <el-table-column prop="average_time" label="平均时长">
            <template #default="scope">{{ scope.row.average_time }}小时</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="打手下单榜" name="dasherOrders">
        <div class="table-toolbar">
          <div>
            <div class="toolbar-title">打手下单榜单</div>
            <div class="toolbar-sub">{{ dasherOrderMeta.period_label || '本月' }}被老板下单最多的打手排行</div>
          </div>
          <el-radio-group v-model="dasherOrderPeriod" size="small" @change="loadDasherOrderRanking">
            <el-radio-button label="week">本周</el-radio-button>
            <el-radio-button label="month">本月</el-radio-button>
            <el-radio-button label="year">本年</el-radio-button>
          </el-radio-group>
        </div>
        <el-table v-loading="dasherOrderLoading" :data="dasherOrderRanking" border style="width: 100%">
          <el-table-column prop="rank" label="排名" width="80">
            <template #default="scope">
              <el-tag v-if="scope.row.rank === 1" type="danger">1</el-tag>
              <el-tag v-else-if="scope.row.rank === 2" type="warning">2</el-tag>
              <el-tag v-else-if="scope.row.rank === 3" type="success">3</el-tag>
              <span v-else>{{ scope.row.rank }}</span>
            </template>
          </el-table-column>
          <el-table-column label="打手" min-width="180">
            <template #default="scope">
              <div class="employee-cell">
                <el-avatar :size="34" :src="scope.row.employee_avatar" />
                <span>{{ scope.row.employee_name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="level_num" label="等级" width="100">
            <template #default="scope">Lv.{{ scope.row.level_num || 0 }}</template>
          </el-table-column>
          <el-table-column prop="order_count" label="下单数" width="120">
            <template #default="scope">{{ scope.row.order_count || 0 }} 单</template>
          </el-table-column>
          <el-table-column prop="total_amount" label="订单金额" width="140">
            <template #default="scope">¥{{ scope.row.total_amount || 0 }}</template>
          </el-table-column>
          <el-table-column label="统计周期" min-width="160">
            <template #default>{{ dasherOrderMeta.start_date || '-' }} 至 {{ dasherOrderMeta.end_date || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="scope">
              <el-button type="primary" link @click="openDasherOrderDetail(scope.row)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="客户分析" name="customers">
        <div class="chart-section">
          <el-card>
            <template #header>客户增长趋势</template>
            <div ref="customerGrowthChart" class="chart"></div>
          </el-card>
          <el-card>
            <template #header>客户等级分布</template>
            <div ref="customerLevelChart" class="chart"></div>
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="detailVisible" title="打手下单详情" width="900px">
      <el-descriptions :column="3" border class="detail-summary">
        <el-descriptions-item label="打手">{{ currentDasherDetail.employee_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="周期">{{ currentDasherDetail.period_label || '-' }}</el-descriptions-item>
        <el-descriptions-item label="订单数">{{ currentDasherDetail.order_count || 0 }} 单</el-descriptions-item>
      </el-descriptions>
      <el-table v-loading="detailLoading" :data="currentDasherDetail.orders || []" border style="width: 100%">
        <el-table-column prop="order_no" label="订单号" min-width="170" />
        <el-table-column prop="customer_name" label="老板" width="130" />
        <el-table-column prop="skill_name" label="技能" width="130" />
        <el-table-column prop="game_name" label="游戏" width="120" />
        <el-table-column prop="status_text" label="状态" width="110">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status_text || getStatusText(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="pay_amount" label="金额" width="110">
          <template #default="scope">¥{{ scope.row.pay_amount || 0 }}</template>
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
  getDasherOrderDetailApi,
  getDasherOrderRankApi,
  getEmployeeRankingApi
} from '@/api/statistics'

const activeTab = ref('orders')
const rankingData = ref([])
const dasherOrderPeriod = ref('month')
const dasherOrderRanking = ref([])
const dasherOrderMeta = ref({})
const dasherOrderLoading = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const currentDasherDetail = ref({})

const orderTrendChart = ref(null)
const orderStatusChart = ref(null)
const revenueTrendChart = ref(null)
const revenuePieChart = ref(null)
const customerGrowthChart = ref(null)
const customerLevelChart = ref(null)

let charts = []

const initCharts = () => {
  charts = [
    echarts.init(orderTrendChart.value),
    echarts.init(orderStatusChart.value),
    echarts.init(revenueTrendChart.value),
    echarts.init(revenuePieChart.value),
    echarts.init(customerGrowthChart.value),
    echarts.init(customerLevelChart.value)
  ]

  charts[0].setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'] },
    yAxis: { type: 'value' },
    series: [{
      data: [120, 180, 150, 220, 280, 350, 300],
      type: 'bar',
      itemStyle: { color: '#409eff' }
    }]
  })

  charts[1].setOption({
    tooltip: { trigger: 'item' },
    series: [{
      data: [
        { value: 40, name: '待支付' },
        { value: 20, name: '待分配' },
        { value: 80, name: '进行中' },
        { value: 150, name: '已完成' },
        { value: 10, name: '已取消' }
      ],
      type: 'pie',
      radius: '60%'
    }]
  })

  charts[2].setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] },
    yAxis: { type: 'value' },
    series: [{
      data: [5000, 8000, 6500, 9000, 12000, 10000],
      type: 'line',
      smooth: true,
      areaStyle: {}
    }]
  })

  charts[3].setOption({
    tooltip: { trigger: 'item' },
    series: [{
      data: [
        { value: 50, name: '王者荣耀' },
        { value: 30, name: '英雄联盟' },
        { value: 15, name: '和平精英' },
        { value: 5, name: '其他' }
      ],
      type: 'pie',
      radius: ['40%', '70%']
    }]
  })

  charts[4].setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] },
    yAxis: { type: 'value' },
    series: [{
      data: [100, 150, 200, 180, 250, 300],
      type: 'bar',
      itemStyle: { color: '#67c23a' }
    }]
  })

  charts[5].setOption({
    tooltip: { trigger: 'item' },
    series: [{
      data: [
        { value: 60, name: '普通客户' },
        { value: 30, name: 'VIP' },
        { value: 10, name: 'SVIP' }
      ],
      type: 'pie',
      radius: '60%'
    }]
  })
}

const loadRanking = async () => {
  try {
    const res = await getEmployeeRankingApi({ limit: 20 })
    rankingData.value = (res.data.results || res.data || []).map((item, index) => ({
      ...item,
      rank: item.rank || index + 1,
      name: item.name || item.employee_name,
      revenue: item.revenue ?? item.total_amount ?? 0,
      rating: item.rating ?? item.avg_rating ?? '-',
      average_time: item.average_time ?? ((item.total_duration || 0) / 60).toFixed(1)
    }))
  } catch (error) { console.error('获取排行失败', error) }
}

const loadDasherOrderRanking = async () => {
  dasherOrderLoading.value = true
  try {
    const res = await getDasherOrderRankApi({
      period: dasherOrderPeriod.value,
      limit: 20
    })
    dasherOrderMeta.value = res.data || {}
    dasherOrderRanking.value = res.data.results || []
  } catch (error) {
    console.error('获取打手下单榜失败', error)
  } finally {
    dasherOrderLoading.value = false
  }
}

const openDasherOrderDetail = async (row) => {
  detailVisible.value = true
  detailLoading.value = true
  currentDasherDetail.value = {
    employee_id: row.employee_id,
    employee_name: row.employee_name,
    period_label: dasherOrderMeta.value.period_label,
    order_count: row.order_count,
    orders: []
  }
  try {
    const res = await getDasherOrderDetailApi({
      employee_id: row.employee_id,
      period: dasherOrderPeriod.value
    })
    currentDasherDetail.value = res.data || currentDasherDetail.value
  } catch (error) {
    console.error('获取打手下单详情失败', error)
  } finally {
    detailLoading.value = false
  }
}

const getStatusType = (status) => {
  const map = {
    published: 'info',
    transferring: 'warning',
    claimed: 'primary',
    confirming: 'warning',
    in_progress: 'primary',
    completed: 'success',
    reviewed: 'success',
    cancelled: 'danger'
  }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = {
    published: '可领取',
    transferring: '转单中',
    claimed: '待开始',
    confirming: '待客户确认',
    in_progress: '进行中',
    completed: '已结束',
    reviewed: '已评价',
    cancelled: '已取消'
  }
  return map[status] || status
}

onMounted(() => { initCharts(); loadRanking(); loadDasherOrderRanking() })
onUnmounted(() => { charts.forEach(c => c?.dispose()) })
</script>

<style scoped>
.statistics-page { padding: 20px; }
.chart-section { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.chart { width: 100%; height: 300px; }
.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.toolbar-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.toolbar-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
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
.detail-summary { margin-bottom: 16px; }
</style>
