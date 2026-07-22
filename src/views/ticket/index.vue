<template>
  <div class="ticket-page">
    <div class="search-bar">
      <el-input v-model="searchForm.keyword" placeholder="搜索工单号/订单号/客户名" clearable style="width: 240px" @keyup.enter="loadData">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="searchForm.status" placeholder="工单状态" clearable style="width: 120px">
        <el-option label="待处理" value="open" />
        <el-option label="处理中" value="in_progress" />
        <el-option label="已关闭" value="closed" />
      </el-select>
      <el-button type="primary" @click="loadData">搜索</el-button>
    </div>

    <el-card>
      <el-table :data="tableData" border style="width: 100%">
        <el-table-column prop="ticket_no" label="工单号" width="200" />
        <el-table-column prop="order_no" label="订单号" width="200" />
        <el-table-column prop="customer_name" label="客户" width="120" />
        <el-table-column prop="employee_name" label="打手" width="120" />
        <el-table-column prop="title" label="工单标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status_text }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="handler_name" label="处理人" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button type="primary" size="small" @click="viewDetail(scope.row)">详情</el-button>
            <el-button v-if="scope.row.status !== 'closed'" type="success" size="small" @click="handleClose(scope.row)">关闭工单</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        layout="total, prev, pager, next, jumper"
        @current-change="handlePageChange"
        style="margin-top: 20px; text-align: right"
      />
    </el-card>

    <!-- 工单详情弹窗 -->
    <el-dialog title="工单详情" :visible.sync="detailVisible" width="700px">
      <div v-if="currentTicket" class="ticket-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="工单号">{{ currentTicket.ticket_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentTicket.status)">{{ currentTicket.status_text }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="订单号">{{ currentTicket.order_no }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ currentTicket.customer_name }}</el-descriptions-item>
          <el-descriptions-item label="打手">{{ currentTicket.employee_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="处理人">{{ currentTicket.handler_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">{{ currentTicket.created_at }}</el-descriptions-item>
          <el-descriptions-item label="关闭时间" :span="2">{{ currentTicket.closed_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="section-title">工单描述</div>
        <div class="section-content">{{ currentTicket.description || '无' }}</div>

        <div class="section-title">处理备注</div>
        <div class="section-content">{{ currentTicket.handle_remark || '无' }}</div>

        <div v-if="currentTicket.order_snapshot" class="section-title">订单快照</div>
        <el-descriptions v-if="currentTicket.order_snapshot" :column="2" border size="small">
          <el-descriptions-item label="订单号">{{ currentTicket.order_snapshot.order_no }}</el-descriptions-item>
          <el-descriptions-item label="订单状态">{{ currentTicket.order_snapshot.status_display }}</el-descriptions-item>
          <el-descriptions-item label="游戏">{{ currentTicket.order_snapshot.game_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="区服">{{ currentTicket.order_snapshot.server || '-' }}</el-descriptions-item>
          <el-descriptions-item label="时长">{{ currentTicket.order_snapshot.duration }}分钟</el-descriptions-item>
          <el-descriptions-item label="人数">{{ currentTicket.order_snapshot.quantity }}</el-descriptions-item>
          <el-descriptions-item label="单价">¥{{ currentTicket.order_snapshot.unit_price }}</el-descriptions-item>
          <el-descriptions-item label="实付">¥{{ currentTicket.order_snapshot.pay_amount }}</el-descriptions-item>
          <el-descriptions-item label="支付方式">{{ currentTicket.order_snapshot.pay_method }}</el-descriptions-item>
          <el-descriptions-item label="下单时间">{{ currentTicket.order_snapshot.created_at }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="currentTicket.order_snapshot && currentTicket.order_snapshot.members && currentTicket.order_snapshot.members.length" class="section-title">接单打手</div>
        <el-table v-if="currentTicket.order_snapshot && currentTicket.order_snapshot.members" :data="currentTicket.order_snapshot.members" border size="small" style="margin-bottom: 16px">
          <el-table-column prop="employee_name" label="打手" />
          <el-table-column prop="skill_name" label="技能" />
          <el-table-column prop="unit_price" label="单价" width="100">
            <template #default="scope">¥{{ scope.row.unit_price }}</template>
          </el-table-column>
          <el-table-column prop="duration" label="时长" width="80" />
          <el-table-column prop="amount" label="金额" width="100">
            <template #default="scope">¥{{ scope.row.amount }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80" />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="currentTicket && currentTicket.status !== 'closed'" type="success" @click="handleClose(currentTicket)">关闭工单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import request from '@/utils/request'

const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchForm = reactive({ keyword: '', status: '' })
const detailVisible = ref(false)
const currentTicket = ref(null)

const loadData = async () => {
  const params = { page: page.value, page_size: pageSize.value }
  if (searchForm.keyword) params.search = searchForm.keyword
  if (searchForm.status) params.status = searchForm.status
  const res = await request.get('/order/tickets/', { params })
  tableData.value = res.data.results || res.data.data || []
  total.value = res.data.count || tableData.value.length
}

const handlePageChange = (p) => {
  page.value = p
  loadData()
}

const getStatusType = (status) => {
  const map = { open: 'danger', in_progress: 'warning', closed: 'success' }
  return map[status] || 'info'
}

const viewDetail = async (row) => {
  const res = await request.get(`/order/tickets/${row.id}/`)
  currentTicket.value = res.data.data || res.data
  detailVisible.value = true
}

const handleClose = async (row) => {
  try {
    const { value: remark } = await ElMessageBox.prompt('请输入处理备注（可选）', '关闭工单', {
      inputPlaceholder: '处理备注',
      confirmButtonText: '确认关闭',
      cancelButtonText: '取消',
      inputType: 'textarea',
    })
    await request.post(`/order/tickets/${row.id}/close/`, { remark: remark || '' })
    ElMessage.success('工单已关闭')
    detailVisible.value = false
    loadData()
  } catch (e) {
    // user cancelled
  }
}

onMounted(loadData)
</script>

<style scoped>
.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.ticket-detail {
  max-height: 60vh;
  overflow-y: auto;
}
.section-title {
  font-weight: 600;
  margin: 16px 0 8px;
  color: #303133;
}
.section-content {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  color: #606266;
  white-space: pre-wrap;
}
</style>
