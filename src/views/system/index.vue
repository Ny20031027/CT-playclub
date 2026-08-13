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
      <el-tab-pane label="欢迎/关键词" name="welcomeKeyword">
        <div class="welcome-section">
          <h3>客服欢迎语</h3>
          <p class="section-desc">客户进入客服聊天时自动发送的欢迎消息</p>
          <el-input v-model="welcomeForm.welcome_text" type="textarea" :rows="3" placeholder="请输入欢迎语内容" />
          <div style="margin-top: 10px;">
            <el-switch v-model="welcomeForm.is_enabled" active-text="启用" inactive-text="禁用" />
            <el-button type="primary" style="margin-left: 20px;" @click="saveWelcome">保存欢迎语</el-button>
          </div>
        </div>
        <el-divider />
        <div class="welcome-section">
          <h3>打手默认快捷欢迎语</h3>
          <p class="section-desc">打手未设置个人快捷欢迎语时，订单群一键发送此默认文案</p>
          <el-input v-model="dasherQuickWelcomeText" type="textarea" :rows="3" placeholder="请输入打手默认快捷欢迎语" maxlength="300" show-word-limit />
          <div style="margin-top: 10px;">
            <el-button type="primary" @click="saveDasherQuickWelcome">保存默认快捷信息</el-button>
          </div>
        </div>
        <el-divider />
        <div class="keyword-section">
          <h3>关键词自动回复</h3>
          <p class="section-desc">当客户消息包含指定关键词时，系统自动回复预设内容</p>
          <el-button type="success" @click="openKeywordModal()">新增规则</el-button>
          <el-table :data="keywordList" border style="width: 100%; margin-top: 10px">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="keyword" label="关键词" />
            <el-table-column prop="reply_text" label="回复内容" show-overflow-tooltip />
            <el-table-column prop="match_type_display" label="匹配方式" width="100" />
            <el-table-column prop="sort" label="排序" width="80" />
            <el-table-column label="状态" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.is_enabled ? 'success' : 'info'">{{ scope.row.is_enabled ? '启用' : '禁用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="scope">
                <el-button type="primary" size="small" @click="openKeywordModal(scope.row)">编辑</el-button>
                <el-button type="danger" size="small" @click="handleDeleteKeyword(scope.row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
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
    <el-dialog :title="isKeywordEdit ? '编辑关键词规则' : '新增关键词规则'" :visible.sync="keywordDialogVisible" width="550px">
      <el-form :model="keywordForm" label-width="90px">
        <el-form-item label="关键词">
          <el-input v-model="keywordForm.keyword" placeholder="请输入关键词" />
        </el-form-item>
        <el-form-item label="回复内容">
          <el-input v-model="keywordForm.reply_text" type="textarea" :rows="3" placeholder="请输入自动回复内容" />
        </el-form-item>
        <el-form-item label="匹配方式">
          <el-select v-model="keywordForm.match_type" style="width: 100%">
            <el-option label="包含" value="contains" />
            <el-option label="完全匹配" value="exact" />
            <el-option label="开头匹配" value="startswith" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="keywordForm.sort" :min="0" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="keywordForm.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="keywordDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitKeyword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConfigListApi, createConfigApi, updateConfigApi, deleteConfigApi, batchUpdateConfigApi } from '@/api/system'
import { getDictionaryListApi, createDictionaryApi, updateDictionaryApi, deleteDictionaryApi } from '@/api/system'
import { getOperationLogApi, getErrorLogApi } from '@/api/system'
import { getCsWelcomeApi, saveCsWelcomeApi, updateCsWelcomeApi } from '@/api/system'
import { getCsKeywordListApi, createCsKeywordApi, updateCsKeywordApi, deleteCsKeywordApi } from '@/api/system'

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
const dasherQuickWelcomeText = ref('')

// 欢迎语相关
const welcomeForm = reactive({ id: null, welcome_text: '', is_enabled: true })

// 关键词规则相关
const keywordList = ref([])
const keywordDialogVisible = ref(false)
const isKeywordEdit = ref(false)
const keywordForm = reactive({ id: null, keyword: '', reply_text: '', match_type: 'contains', sort: 0, is_enabled: true })

const loadConfig = async () => {
  try {
    const res = await getConfigListApi()
    configList.value = res.data.results || []
    const quick = configList.value.find(item => item.key === 'dasher_default_quick_welcome_message')
    dasherQuickWelcomeText.value = quick ? (quick.value || '') : ''
  }
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

const loadWelcome = async () => {
  try {
    const res = await getCsWelcomeApi()
    if (res.data && res.data.id) {
      welcomeForm.id = res.data.id
      welcomeForm.welcome_text = res.data.welcome_text || ''
      welcomeForm.is_enabled = res.data.is_enabled !== false
    }
  } catch (error) { console.error('获取欢迎语失败', error) }
}

const saveWelcome = async () => {
  try {
    if (welcomeForm.id) {
      await updateCsWelcomeApi(welcomeForm.id, {
        welcome_text: welcomeForm.welcome_text,
        is_enabled: welcomeForm.is_enabled,
      })
    } else {
      const res = await saveCsWelcomeApi({
        welcome_text: welcomeForm.welcome_text,
        is_enabled: welcomeForm.is_enabled,
      })
      if (res.data && res.data.id) {
        welcomeForm.id = res.data.id
      }
    }
    ElMessage.success('保存成功')
  } catch (error) { ElMessage.error('保存失败') }
}

const saveDasherQuickWelcome = async () => {
  try {
    await batchUpdateConfigApi({
      dasher_default_quick_welcome_message: dasherQuickWelcomeText.value || '',
    })
    ElMessage.success('保存成功')
    loadConfig()
  } catch (error) { ElMessage.error('保存失败') }
}

const loadKeywords = async () => {
  try {
    const res = await getCsKeywordListApi()
    keywordList.value = res.data.results || []
  } catch (error) { console.error('获取关键词规则失败', error) }
}

const openKeywordModal = (row) => {
  isKeywordEdit.value = !!row
  if (row) {
    Object.assign(keywordForm, { id: row.id, keyword: row.keyword, reply_text: row.reply_text, match_type: row.match_type, sort: row.sort, is_enabled: row.is_enabled })
  } else {
    Object.assign(keywordForm, { id: null, keyword: '', reply_text: '', match_type: 'contains', sort: 0, is_enabled: true })
  }
  keywordDialogVisible.value = true
}

const handleSubmitKeyword = async () => {
  try {
    if (isKeywordEdit.value) {
      await updateCsKeywordApi(keywordForm.id, { ...keywordForm })
    } else {
      await createCsKeywordApi({ ...keywordForm })
    }
    ElMessage.success('操作成功')
    keywordDialogVisible.value = false
    loadKeywords()
  } catch (error) { ElMessage.error('操作失败') }
}

const handleDeleteKeyword = async (row) => {
  try {
    await deleteCsKeywordApi(row.id)
    ElMessage.success('删除成功')
    loadKeywords()
  } catch (error) { ElMessage.error('删除失败') }
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
onMounted(() => { loadConfig(); loadDictionary(); loadLogs(); loadErrorLogs(); loadWelcome(); loadKeywords() })
</script>

<style scoped>
.system-page { padding: 20px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 20px; }
.welcome-section { margin-bottom: 10px; }
.welcome-section h3 { margin: 0 0 8px 0; font-size: 16px; color: #303133; }
.section-desc { color: #909399; font-size: 13px; margin: 0 0 12px 0; }
.keyword-section h3 { margin: 0 0 8px 0; font-size: 16px; color: #303133; }
</style>
