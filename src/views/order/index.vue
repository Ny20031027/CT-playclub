<template>
  <div class="order-page">
    <div class="search-bar">
      <el-input v-model="searchForm.keyword" placeholder="搜索订单号/客户名" clearable style="width: 200px" @keyup.enter="loadData">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="searchForm.status" placeholder="订单状态" clearable style="width: 120px">
        <el-option label="待支付" value="pending_payment" />
        <el-option label="待分配" value="pending_assign" />
        <el-option label="进行中" value="in_progress" />
        <el-option label="已完成" value="completed" />
        <el-option label="已取消" value="canceled" />
        <el-option label="已退款" value="refunded" />
      </el-select>
      <el-date-picker v-model="searchForm.date" type="date" placeholder="选择日期" />
      <el-button type="primary" @click="loadData">搜索</el-button>
      <el-button type="success" @click="openAddModal">创建订单</el-button>
    </div>
    <el-card>
      <el-table :data="tableData" border style="width: 100%">
        <el-table-column prop="order_no" label="订单号" />
        <el-table-column prop="customer_name" label="客户" />
        <el-table-column prop="employee_name" label="陪玩师" />
        <el-table-column prop="game" label="游戏" />
        <el-table-column prop="duration" label="时长" width="80">
          <template #default="scope">{{ scope.row.duration }}小时</template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="100">
          <template #default="scope">¥{{ scope.row.amount }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">{{ getStatusText(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" />
        <el-table-column label="操作" width="300">
          <template #default="scope">
            <el-button type="primary" size="small" @click="viewDetail(scope.row)">详情</el-button>
            <el-button v-if="scope.row.status === 'pending_assign'" type="success" size="small" @click="handleAssign(scope.row)">派单</el-button>
            <el-button v-if="scope.row.status === 'in_progress'" type="success" size="small" @click="handleComplete(scope.row)">完成</el-button>
            <el-button v-if="scope.row.status === 'pending_payment'" type="warning" size="small" @click="handleCancel(scope.row)">取消</el-button>
            <el-button v-if="scope.row.status === 'completed'" type="danger" size="small" @click="handleRefund(scope.row)">退款</el-button>
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
    <el-dialog :title="isEdit ? '编辑订单' : '创建订单'" :visible.sync="dialogVisible" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="客户" prop="customer">
          <el-select v-model="form.customer" placeholder="选择客户">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="陪玩师" prop="employee">
          <el-select v-model="form.employee" placeholder="选择陪玩师">
            <el-option v-for="e in employees" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="游戏" prop="game">
          <el-select v-model="form.game">
            <el-option label="王者荣耀" value="王者荣耀" />
            <el-option label="英雄联盟" value="英雄联盟" />
            <el-option label="和平精英" value="和平精英" />
          </el-select>
        </el-form-item>
        <el-form-item label="时长(小时)" prop="duration">
          <el-input-number v-model="form.duration" :min="1" :max="24" />
        </el-form-item>
        <el-form-item label="金额" prop="amount">
          <el-input-number v-model="form.amount" :min="0" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { getOrderListApi, createOrderApi, updateOrderApi, deleteOrderApi, assignOrderApi, completeOrderApi, cancelOrderApi, refundOrderApi } from '@/api/order'
import { getCustomerListApi } from '@/api/customer'
import { getEmployeeListApi } from '@/api/employee'

const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const customers = ref([])
const employees = ref([])

const searchForm = reactive({ keyword: '', status: '', date: '' })
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({ id: null, customer: null, employee: null, game: '', duration: 1, amount: 0 })

const rules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  employee: [{ required: true, message: '请选择陪玩师', trigger: 'change' }],
  game: [{ required: true, message: '请选择游戏', trigger: 'change' }],
  duration: [{ required: true, message: '请输入时长', trigger: 'blur' }],
  amount: [{ required: true, message: '请输入金额', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const map = { pending_payment: 'warning', pending_assign: 'info', in_progress: 'primary', completed: 'success', canceled: 'danger', refunded: 'danger' }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = { pending_payment: '待支付', pending_assign: '待分配', in_progress: '进行中', completed: '已完成', canceled: '已取消', refunded: '已退款' }
  return map[status] || status
}

const loadData = async () => {
  try {
    const res = await getOrderListApi({ page: page.value, page_size: pageSize.value, ...searchForm })
    tableData.value = res.data.results || []
    total.value = res.data.count || 0
  } catch (error) { console.error('获取订单列表失败', error) }
}

const loadOptions = async () => {
  try {
    const [cRes, eRes] = await Promise.all([getCustomerListApi({ page_size: 100 }), getEmployeeListApi({ page_size: 100 })])
    customers.value = cRes.data.results || []
    employees.value = eRes.data.results || []
  } catch (error) { console.error('获取选项失败', error) }
}

const openAddModal = () => {
  isEdit.value = false
  Object.assign(form, { id: null, customer: null, employee: null, game: '', duration: 1, amount: 0 })
  dialogVisible.value = true
}

const viewDetail = (row) => { ElMessage.info(`查看订单: ${row.order_no}`) }

const handleAssign = async (row) => {
  try { await assignOrderApi(row.id, { employee: row.employee }); ElMessage.success('派单成功'); loadData() }
  catch (error) { ElMessage.error('派单失败') }
}

const handleComplete = async (row) => {
  try { await completeOrderApi(row.id); ElMessage.success('订单已完成'); loadData() }
  catch (error) { ElMessage.error('操作失败') }
}

const handleCancel = async (row) => {
  try { await cancelOrderApi(row.id); ElMessage.success('订单已取消'); loadData() }
  catch (error) { ElMessage.error('操作失败') }
}

const handleRefund = async (row) => {
  try { await refundOrderApi(row.id, { amount: row.amount }); ElMessage.success('退款成功'); loadData() }
  catch (error) { ElMessage.error('退款失败') }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate()
  if (!valid) return
  try {
    if (isEdit.value) { await updateOrderApi(form.id, form); ElMessage.success('更新成功') }
    else { await createOrderApi(form); ElMessage.success('创建成功') }
    dialogVisible.value = false
    loadData()
  } catch (error) { ElMessage.error('操作失败') }
}

const handlePageChange = (val) => { page.value = val; loadData() }
onMounted(() => { loadData(); loadOptions() })
</script>

<style scoped>
.order-page { padding: 20px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 20px; }
</style>
