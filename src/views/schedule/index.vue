<template>
  <div class="schedule-page">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="今日排班" name="today">
        <div class="schedule-header">
          <el-date-picker v-model="currentDate" type="date" @change="loadSchedule" />
          <el-button type="success" @click="openAddModal">新增排班</el-button>
        </div>
        <el-table :data="scheduleList" border style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="employee_name" label="陪玩师" />
          <el-table-column prop="shift_name" label="班次" />
          <el-table-column prop="start_time" label="开始时间" />
          <el-table-column prop="end_time" label="结束时间" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
              <el-tag :type="getStatusType(scope.row.status)">{{ getStatusText(scope.row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="scope">
              <el-button type="primary" size="small" @click="openEditModal(scope.row)">编辑</el-button>
              <el-button type="danger" size="small" @click="handleDelete(scope.row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="请假管理" name="leave">
        <el-table :data="leaveList" border style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="employee_name" label="陪玩师" />
          <el-table-column prop="start_date" label="开始日期" />
          <el-table-column prop="end_date" label="结束日期" />
          <el-table-column prop="reason" label="原因" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
              <el-tag :type="getStatusType(scope.row.status)">{{ getStatusText(scope.row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="scope">
              <el-button v-if="scope.row.status === 'pending'" type="success" size="small" @click="handleApproveLeave(scope.row)">批准</el-button>
              <el-button v-if="scope.row.status === 'pending'" type="danger" size="small" @click="handleRejectLeave(scope.row)">拒绝</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="考勤记录" name="attendance">
        <el-table :data="attendanceList" border style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="employee_name" label="陪玩师" />
          <el-table-column prop="date" label="日期" />
          <el-table-column prop="check_in" label="上班打卡" />
          <el-table-column prop="check_out" label="下班打卡" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.status === 'normal' ? 'success' : 'danger'">
                {{ scope.row.status === 'normal' ? '正常' : '异常' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="班次管理" name="shifts">
        <el-button type="success" @click="openShiftModal">新增班次</el-button>
        <el-table :data="shiftList" border style="width: 100%; margin-top: 10px">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="班次名称" />
          <el-table-column prop="start_time" label="开始时间" />
          <el-table-column prop="end_time" label="结束时间" />
          <el-table-column prop="work_hours" label="工时" />
          <el-table-column label="操作" width="150">
            <template #default="scope">
              <el-button type="danger" size="small" @click="handleDeleteShift(scope.row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
    <el-dialog :title="isEdit ? '编辑排班' : '新增排班'" :visible.sync="dialogVisible" width="450px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="陪玩师" prop="employee">
          <el-select v-model="form.employee" placeholder="选择陪玩师">
            <el-option v-for="e in employees" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="班次" prop="shift">
          <el-select v-model="form.shift" placeholder="选择班次">
            <el-option v-for="s in shiftList" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期" prop="date">
          <el-date-picker v-model="form.date" type="date" />
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
import { getScheduleListApi, createScheduleApi, updateScheduleApi, deleteScheduleApi } from '@/api/schedule'
import { getLeaveListApi, approveLeaveApi } from '@/api/schedule'
import { getAttendanceListApi, getShiftListApi, createShiftApi, deleteShiftApi } from '@/api/schedule'
import { getEmployeeListApi } from '@/api/employee'

const activeTab = ref('today')
const currentDate = ref(new Date())
const scheduleList = ref([])
const leaveList = ref([])
const attendanceList = ref([])
const shiftList = ref([])
const employees = ref([])

const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({ id: null, employee: null, shift: null, date: new Date() })

const rules = {
  employee: [{ required: true, message: '请选择陪玩师', trigger: 'change' }],
  shift: [{ required: true, message: '请选择班次', trigger: 'change' }],
  date: [{ required: true, message: '请选择日期', trigger: 'change' }]
}

const getStatusType = (status) => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger', completed: 'primary', normal: 'success' }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = { pending: '待审核', approved: '已批准', rejected: '已拒绝', completed: '已完成', normal: '正常' }
  return map[status] || status
}

const loadSchedule = async () => {
  try {
    const res = await getScheduleListApi({ date: currentDate.value })
    scheduleList.value = res.data.results || []
  } catch (error) { console.error('获取排班失败', error) }
}

const loadLeave = async () => {
  try { const res = await getLeaveListApi(); leaveList.value = res.data.results || [] }
  catch (error) { console.error('获取请假记录失败', error) }
}

const loadAttendance = async () => {
  try { const res = await getAttendanceListApi(); attendanceList.value = res.data.results || [] }
  catch (error) { console.error('获取考勤失败', error) }
}

const loadShifts = async () => {
  try { const res = await getShiftListApi(); shiftList.value = res.data.results || [] }
  catch (error) { console.error('获取班次失败', error) }
}

const loadEmployees = async () => {
  try { const res = await getEmployeeListApi({ page_size: 100 }); employees.value = res.data.results || [] }
  catch (error) { console.error('获取陪玩师失败', error) }
}

const openAddModal = () => {
  isEdit.value = false
  Object.assign(form, { id: null, employee: null, shift: null, date: currentDate.value })
  dialogVisible.value = true
}

const openEditModal = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, employee: row.employee, shift: row.shift, date: row.date })
  dialogVisible.value = true
}

const openShiftModal = () => { ElMessage.info('新增班次功能开发中') }

const handleDelete = async (row) => {
  try { await deleteScheduleApi(row.id); ElMessage.success('删除成功'); loadSchedule() }
  catch (error) { ElMessage.error('删除失败') }
}

const handleDeleteShift = async (row) => {
  try { await deleteShiftApi(row.id); ElMessage.success('删除成功'); loadShifts() }
  catch (error) { ElMessage.error('删除失败') }
}

const handleApproveLeave = async (row) => {
  try { await approveLeaveApi(row.id); ElMessage.success('批准成功'); loadLeave() }
  catch (error) { ElMessage.error('操作失败') }
}

const handleRejectLeave = (row) => { ElMessage.info('拒绝功能开发中') }

const handleSubmit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate()
  if (!valid) return
  try {
    if (isEdit.value) { await updateScheduleApi(form.id, form); ElMessage.success('更新成功') }
    else { await createScheduleApi(form); ElMessage.success('创建成功') }
    dialogVisible.value = false
    loadSchedule()
  } catch (error) { ElMessage.error('操作失败') }
}

onMounted(() => { loadSchedule(); loadLeave(); loadAttendance(); loadShifts(); loadEmployees() })
</script>

<style scoped>
.schedule-page { padding: 20px; }
.schedule-header { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; }
</style>
