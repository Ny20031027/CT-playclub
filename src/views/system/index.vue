<template>
  <div class="system-page">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="系统配置" name="config">
        <el-button type="success" @click="openAddModal">新增配置</el-button>
        <el-table :data="configList" border style="width: 100%; margin-top: 10px">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="key" label="配置键" />
          <el-table-column prop="value" label="配置值" />
          <el-table-column prop="description" label="描述" />
          <el-table-column label="操作" width="150">
            <template #default="scope">
              <el-button type="primary" size="small" @click="openEditModal(scope.row)">编辑</el-button>
              <el-button type="danger" size="small" @click="handleDelete(scope.row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="数据字典" name="dictionary">
        <el-button type="success" @click="openAddModal">新增字典</el-button>
        <el-table :data="dictionaryList" border style="width: 100%; margin-top: 10px">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="type" label="类型" />
          <el-table-column prop="key" label="键" />
          <el-table-column prop="value" label="值" />
          <el-table-column prop="description" label="描述" />
          <el-table-column label="操作" width="150">
            <template #default="scope">
              <el-button type="primary" size="small" @click="openEditModal(scope.row)">编辑</el-button>
              <el-button type="danger" size="small" @click="handleDelete(scope.row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="操作日志" name="operation">
        <div class="search-bar">
          <el-input v-model="searchForm.keyword" placeholder="搜索操作" clearable style="width: 200px" />
          <el-date-picker v-model="searchForm.date" type="date" placeholder="选择日期" />
          <el-button type="primary" @click="loadLogs">搜索</el-button>
        </div>
        <el-table :data="operationLogs" border style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="user_name" label="操作人" />
          <el-table-column prop="action" label="操作" />
          <el-table-column prop="target" label="目标" />
          <el-table-column prop="created_at" label="时间" />
        </el-table>
        <el-pagination :total="logTotal" :page-size="pageSize" :current-page="page" layout="total, prev, pager, next, jumper" @current-change="handlePageChange" style="margin-top: 20px; text-align: right" />
      </el-tab-pane>
      <el-tab-pane label="错误日志" name="error">
        <el-table :data="errorLogs" border style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="error_type" label="错误类型" />
          <el-table-column prop="message" label="错误信息" />
          <el-table-column prop="path" label="请求路径" />
          <el-table-column prop="created_at" label="时间" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
    <el-dialog :title="isEdit ? '编辑' : '新增'" :visible.sync="dialogVisible" width="450px">
      <el-form ref="formRef" :model="form" label-width="80px">
        <el-form-item label="键" prop="key">
          <el-input v-model="form.key" />
        </el-form-item>
        <el-form-item label="值" prop="value">
          <el-input v-model="form.value" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" />
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
import { getConfigListApi, createConfigApi, updateConfigApi, deleteConfigApi } from '@/api/system'
import { getDictionaryListApi, createDictionaryApi, updateDictionaryApi, deleteDictionaryApi } from '@/api/system'
import { getOperationLogApi, getErrorLogApi } from '@/api/system'

const activeTab = ref('config')
const configList = ref([])
const dictionaryList = ref([])
const operationLogs = ref([])
const errorLogs = ref([])
const logTotal = ref(0)
const page = ref(1)
const pageSize = ref(10)

const searchForm = reactive({ keyword: '', date: '' })
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({ id: null, key: '', value: '', description: '' })

const loadConfig = async () => {
  try { const res = await getConfigListApi(); configList.value = res.data.results || [] }
  catch (error) { console.error('获取配置失败', error) }
}

const loadDictionary = async () => {
  try { const res = await getDictionaryListApi(); dictionaryList.value = res.data.results || [] }
  catch (error) { console.error('获取字典失败', error) }
}

const loadLogs = async () => {
  try {
    const res = await getOperationLogApi({ page: page.value, page_size: pageSize.value, ...searchForm })
    operationLogs.value = res.data.results || []
    logTotal.value = res.data.count || 0
  } catch (error) { console.error('获取日志失败', error) }
}

const loadErrorLogs = async () => {
  try { const res = await getErrorLogApi(); errorLogs.value = res.data.results || [] }
  catch (error) { console.error('获取错误日志失败', error) }
}

const openAddModal = () => {
  isEdit.value = false
  Object.assign(form, { id: null, key: '', value: '', description: '' })
  dialogVisible.value = true
}

const openEditModal = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, key: row.key, value: row.value, description: row.description })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    if (activeTab.value === 'config') { await deleteConfigApi(row.id) }
    else { await deleteDictionaryApi(row.id) }
    ElMessage.success('删除成功')
    if (activeTab.value === 'config') { loadConfig() }
    else { loadDictionary() }
  } catch (error) { ElMessage.error('删除失败') }
}

const handleSubmit = async () => {
  try {
    if (activeTab.value === 'config') {
      if (isEdit.value) { await updateConfigApi(form.id, form) }
      else { await createConfigApi(form) }
      loadConfig()
    } else {
      if (isEdit.value) { await updateDictionaryApi(form.id, form) }
      else { await createDictionaryApi(form) }
      loadDictionary()
    }
    ElMessage.success('操作成功')
    dialogVisible.value = false
  } catch (error) { ElMessage.error('操作失败') }
}

const handlePageChange = (val) => { page.value = val; loadLogs() }
onMounted(() => { loadConfig(); loadDictionary(); loadLogs(); loadErrorLogs() })
</script>

<style scoped>
.system-page { padding: 20px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 20px; }
</style>
