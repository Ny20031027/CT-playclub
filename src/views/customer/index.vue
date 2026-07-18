<template>
  <div class="customer-page">
    <div class="search-bar">
      <el-input v-model="searchForm.keyword" placeholder="搜索姓名/手机号" clearable style="width: 200px" @keyup.enter="loadData">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="searchForm.level" placeholder="客户等级" clearable style="width: 120px">
        <el-option label="普通" value="normal" />
        <el-option label="VIP" value="vip" />
        <el-option label="SVIP" value="svip" />
      </el-select>
      <el-button type="primary" @click="loadData">搜索</el-button>
      <el-button type="success" @click="openAddModal">新增客户</el-button>
    </div>
    <el-card>
      <el-table :data="tableData" border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="phone" label="手机号" />
        <el-table-column prop="level" label="等级" width="100">
          <template #default="scope">
            <el-tag :type="getLevelType(scope.row.level)">{{ getLevelText(scope.row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_consumption" label="累计消费" width="120">
          <template #default="scope">¥{{ scope.row.total_consumption || 0 }}</template>
        </el-table-column>
        <el-table-column prop="order_count" label="订单数" width="100" />
        <el-table-column prop="is_blacklisted" label="黑名单" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_blacklisted ? 'danger' : 'success'">
              {{ scope.row.is_blacklisted ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" />
        <el-table-column label="操作" width="250">
          <template #default="scope">
            <el-button type="primary" size="small" @click="openEditModal(scope.row)">编辑</el-button>
            <el-button type="warning" size="small" @click="toggleBlacklist(scope.row)">
              {{ scope.row.is_blacklisted ? '移出黑名单' : '加入黑名单' }}
            </el-button>
            <el-button type="danger" size="small" @click="handleDelete(scope.row)">删除</el-button>
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
    <el-dialog :title="isEdit ? '编辑客户' : '新增客户'" :visible.sync="dialogVisible" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="等级" prop="level">
          <el-select v-model="form.level">
            <el-option label="普通" value="normal" />
            <el-option label="VIP" value="vip" />
            <el-option label="SVIP" value="svip" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" />
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
import { getCustomerListApi, createCustomerApi, updateCustomerApi, deleteCustomerApi } from '@/api/customer'

const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const searchForm = reactive({ keyword: '', level: '' })
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({ id: null, name: '', phone: '', level: 'normal', remark: '' })

const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  phone: [{ required: true, message: '请输入手机号', trigger: 'blur' }],
  level: [{ required: true, message: '请选择等级', trigger: 'change' }]
}

const getLevelType = (level) => {
  const map = { normal: 'info', vip: 'warning', svip: 'danger' }
  return map[level] || 'info'
}

const getLevelText = (level) => {
  const map = { normal: '普通', vip: 'VIP', svip: 'SVIP' }
  return map[level] || level
}

const loadData = async () => {
  try {
    const res = await getCustomerListApi({ page: page.value, page_size: pageSize.value, ...searchForm })
    tableData.value = res.data.results || []
    total.value = res.data.count || 0
  } catch (error) { console.error('获取客户列表失败', error) }
}

const openAddModal = () => {
  isEdit.value = false
  Object.assign(form, { id: null, name: '', phone: '', level: 'normal', remark: '' })
  dialogVisible.value = true
}

const openEditModal = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, name: row.name, phone: row.phone, level: row.level, remark: row.remark || '' })
  dialogVisible.value = true
}

const toggleBlacklist = async (row) => {
  try {
    await updateCustomerApi(row.id, { is_blacklisted: !row.is_blacklisted })
    ElMessage.success(row.is_blacklisted ? '已移出黑名单' : '已加入黑名单')
    loadData()
  } catch (error) { ElMessage.error('操作失败') }
}

const handleDelete = async (row) => {
  try {
    await deleteCustomerApi(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) { ElMessage.error('删除失败') }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate()
  if (!valid) return
  try {
    if (isEdit.value) { await updateCustomerApi(form.id, form); ElMessage.success('更新成功') }
    else { await createCustomerApi(form); ElMessage.success('创建成功') }
    dialogVisible.value = false
    loadData()
  } catch (error) { ElMessage.error('操作失败') }
}

const handlePageChange = (val) => { page.value = val; loadData() }
onMounted(loadData)
</script>

<style scoped>
.customer-page { padding: 20px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 20px; }
</style>
