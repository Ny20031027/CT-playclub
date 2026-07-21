<template>
  <div class="employee-page">
    <div class="search-bar">
      <el-input v-model="searchForm.keyword" placeholder="搜索姓名/昵称" clearable style="width: 200px" @keyup.enter="loadData">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="searchForm.status" placeholder="接单状态" clearable style="width: 120px">
        <el-option label="空闲" value="idle" />
        <el-option label="忙碌" value="busy" />
        <el-option label="休息" value="rest" />
      </el-select>
      <el-select v-model="searchForm.gender" placeholder="性别" clearable style="width: 100px">
        <el-option label="男" value="male" />
        <el-option label="女" value="female" />
      </el-select>
      <el-button type="primary" @click="loadData">搜索</el-button>
      <el-button type="success" @click="openAddModal">新增陪玩师</el-button>
    </div>
    <el-card>
      <el-table :data="tableData" border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="avatar" label="头像" width="80">
          <template #default="scope">
            <el-image :src="scope.row.avatar_url || scope.row.avatar" fit="cover" style="width: 48px; height: 48px; border-radius: 50%" />
          </template>
        </el-table-column>
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="nickname" label="昵称" />
        <el-table-column prop="gender" label="性别" width="80">
          <template #default="scope">{{ scope.row.gender === 'male' ? '男' : '女' }}</template>
        </el-table-column>
        <el-table-column prop="age" label="年龄" width="80" />
        <el-table-column prop="status" label="接单状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">{{ getStatusText(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rating" label="评分" width="80" />
        <el-table-column prop="hourly_rate" label="时薪" width="100">
          <template #default="scope">¥{{ scope.row.hourly_rate }}/小时</template>
        </el-table-column>
        <el-table-column prop="created_at" label="入职时间" />
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button type="primary" size="small" @click="openEditModal(scope.row)">编辑</el-button>
            <el-button type="success" size="small" @click="viewDetail(scope.row)">详情</el-button>
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
    <el-dialog :title="isEdit ? '编辑陪玩师' : '新增陪玩师'" :visible.sync="dialogVisible" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="form.nickname" placeholder="请输入昵称" />
        </el-form-item>
        <el-form-item label="性别" prop="gender">
          <el-radio-group v-model="form.gender">
            <el-radio label="male">男</el-radio>
            <el-radio label="female">女</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="年龄" prop="age">
          <el-input-number v-model="form.age" :min="18" :max="60" />
        </el-form-item>
        <el-form-item label="时薪" prop="hourly_rate">
          <el-input-number v-model="form.hourly_rate" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="技能标签">
          <el-select v-model="form.skills" multiple placeholder="请选择技能">
            <el-option label="王者荣耀" value="王者荣耀" />
            <el-option label="英雄联盟" value="英雄联盟" />
            <el-option label="和平精英" value="和平精英" />
            <el-option label="绝地求生" value="绝地求生" />
            <el-option label="Valorant" value="Valorant" />
          </el-select>
        </el-form-item>
        <el-form-item label="自我介绍">
          <el-input v-model="form.introduction" type="textarea" :rows="3" />
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
import { getEmployeeListApi, createEmployeeApi, updateEmployeeApi, deleteEmployeeApi } from '@/api/employee'

const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const searchForm = reactive({
  keyword: '',
  status: '',
  gender: ''
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  name: '',
  nickname: '',
  gender: 'female',
  age: 20,
  hourly_rate: 50,
  skills: [],
  introduction: ''
})

const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  nickname: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
  gender: [{ required: true, message: '请选择性别', trigger: 'change' }],
  age: [{ required: true, message: '请输入年龄', trigger: 'blur' }],
  hourly_rate: [{ required: true, message: '请输入时薪', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const map = { idle: 'success', busy: 'danger', rest: 'warning' }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = { idle: '空闲', busy: '忙碌', rest: '休息' }
  return map[status] || status
}

const loadData = async () => {
  try {
    const res = await getEmployeeListApi({
      page: page.value,
      page_size: pageSize.value,
      keyword: searchForm.keyword,
      status: searchForm.status,
      gender: searchForm.gender
    })
    tableData.value = res.data.results || []
    total.value = res.data.count || 0
  } catch (error) {
    console.error('获取陪玩师列表失败', error)
  }
}

const openAddModal = () => {
  isEdit.value = false
  Object.assign(form, {
    id: null,
    name: '',
    nickname: '',
    gender: 'female',
    age: 20,
    hourly_rate: 50,
    skills: [],
    introduction: ''
  })
  dialogVisible.value = true
}

const openEditModal = (row) => {
  isEdit.value = true
  Object.assign(form, {
    id: row.id,
    name: row.name,
    nickname: row.nickname,
    gender: row.gender,
    age: row.age,
    hourly_rate: row.hourly_rate,
    skills: row.skills || [],
    introduction: row.introduction || ''
  })
  dialogVisible.value = true
}

const viewDetail = (row) => {
  ElMessage.info(`查看陪玩师: ${row.name}`)
}

const handleDelete = async (row) => {
  try {
    await deleteEmployeeApi(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate()
  if (!valid) return

  try {
    if (isEdit.value) {
      await updateEmployeeApi(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createEmployeeApi(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handlePageChange = (val) => {
  page.value = val
  loadData()
}

onMounted(loadData)
</script>

<style scoped>
.employee-page { padding: 20px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 20px; }
</style>
