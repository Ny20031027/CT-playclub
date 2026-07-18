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
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { getEmployeeRankingApi } from '@/api/statistics'

const activeTab = ref('orders')
const rankingData = ref([])

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
    const res = await getEmployeeRankingApi({ page_size: 20 })
    rankingData.value = res.data.results?.map((item, index) => ({ ...item, rank: index + 1 })) || []
  } catch (error) { console.error('获取排行失败', error) }
}

onMounted(() => { initCharts(); loadRanking() })
onUnmounted(() => { charts.forEach(c => c?.dispose()) })
</script>

<style scoped>
.statistics-page { padding: 20px; }
.chart-section { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.chart { width: 100%; height: 300px; }
</style>
