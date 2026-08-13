<template>
  <div class="self-service-page">
    <section class="hero-panel">
      <div>
        <div class="eyebrow">SELF-SERVICE CATALOG</div>
        <h1>自助下单项目</h1>
        <p>以技能为入口，配置玩法、等级、服务和最终可售价格。</p>
      </div>
      <el-button type="primary" size="large" :icon="Plus" @click="openCreate">新建技能项目</el-button>
    </section>

    <section class="metrics-grid">
      <div class="metric-card">
        <span>技能项目</span><strong>{{ rows.length }}</strong><small>全部技能</small>
      </div>
      <div class="metric-card accent">
        <span>已启用自助下单</span><strong>{{ enabledCount }}</strong><small>可在小程序展示</small>
      </div>
      <div class="metric-card">
        <span>玩法数量</span><strong>{{ gameplayCount }}</strong><small>已配置玩法</small>
      </div>
      <div class="metric-card">
        <span>组合价格</span><strong>{{ priceRuleCount }}</strong><small>SKU 覆盖规则</small>
      </div>
    </section>

    <el-card class="catalog-card" shadow="never">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索技能名称或分类"
          :prefix-icon="Search"
          class="search-input"
        />
        <el-radio-group v-model="statusFilter">
          <el-radio-button v-for="item in statusOptions" :key="item.value" :label="item.value">{{ item.label }}</el-radio-button>
        </el-radio-group>
        <el-button :icon="Refresh" @click="loadData">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="filteredRows" row-key="id" class="catalog-table">
        <el-table-column label="技能项目" min-width="220">
          <template #default="{ row }">
            <div class="skill-cell">
              <div class="skill-avatar">{{ row.name?.slice(0, 1) || '技' }}</div>
              <div><b>{{ row.name }}</b><span>{{ row.category || '未设置分类' }}</span></div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="试音" width="110">
          <template #default="{ row }">{{ trialText[row.trial_mode] || '可选试音' }}</template>
        </el-table-column>
        <el-table-column label="玩法" width="90">
          <template #default="{ row }"><b>{{ row.gameplays?.length || 0 }}</b> 个</template>
        </el-table-column>
        <el-table-column label="价格规格" width="110">
          <template #default="{ row }">{{ countRules(row) }} 条</template>
        </el-table-column>
        <el-table-column label="自助下单" width="120">
          <template #default="{ row }">
            <el-tag :type="row.self_service_enabled ? 'success' : 'info'" effect="light">
              {{ row.self_service_enabled ? '已启用' : '未启用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'danger'" effect="plain">{{ row.status ? '上架' : '下架' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="openEdit(row)">配置</el-button>
            <el-button link :icon="CopyDocument" @click="copyProject(row)">复制</el-button>
            <el-button type="danger" link :icon="Delete" @click="removeProject(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" :title="editingId ? '编辑自助下单项目' : '新建自助下单项目'" size="92%" destroy-on-close>
      <div class="drawer-shell">
        <el-steps :active="activeStep" align-center finish-status="success" class="steps">
          <el-step title="技能信息" description="名称、试音与发布设置" @click="activeStep = 0" />
          <el-step title="玩法与规格" description="选项、结算和价格" @click="activeStep = 1" />
          <el-step title="下单预览" description="发布前检查体验" @click="activeStep = 2" />
        </el-steps>

        <div v-show="activeStep === 0" class="step-panel basic-panel">
          <el-form ref="formRef" :model="form" label-position="top" class="basic-form">
            <div class="form-grid">
              <el-form-item label="技能名称" required>
                <el-input v-model="form.name" maxlength="100" show-word-limit placeholder="如：三角洲行动" />
              </el-form-item>
              <el-form-item label="所属分类">
                <el-input v-model="form.category" placeholder="如：射击竞技" />
              </el-form-item>
              <el-form-item label="试音模式">
                <el-radio-group v-model="form.trial_mode">
                  <el-radio-button label="disabled">不支持</el-radio-button>
                  <el-radio-button label="optional">可选</el-radio-button>
                  <el-radio-button label="required">必须</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="排序权重">
                <el-input-number v-model="form.sort" :min="0" :max="9999" controls-position="right" />
              </el-form-item>
            </div>
            <el-form-item label="技能介绍">
              <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
            </el-form-item>
            <el-form-item label="下单须知">
              <el-input v-model="form.order_notice" type="textarea" :rows="3" placeholder="展示给用户的重要规则、退款和服务说明" />
            </el-form-item>
            <el-form-item label="备注输入提示">
              <el-input v-model="form.remark_placeholder" maxlength="200" />
            </el-form-item>
            <div class="switch-row">
              <div><b>启用自助下单</b><span>关闭后配置会保留，但小程序不可下单</span></div>
              <el-switch v-model="form.self_service_enabled" />
            </div>
            <div class="switch-row">
              <div><b>项目上架</b><span>控制技能项目整体是否可用</span></div>
              <el-switch v-model="form.status" />
            </div>
          </el-form>
        </div>

        <div v-show="activeStep === 1" class="step-panel gameplay-layout">
          <aside class="gameplay-sidebar">
            <div class="side-title"><span>玩法列表</span><el-button type="primary" link :icon="Plus" @click="addGameplay">新增</el-button></div>
            <button
              v-for="(gameplay, index) in form.gameplays"
              :key="gameplay._key"
              class="gameplay-nav"
              :class="{ active: activeGameplayIndex === index }"
              @click="activeGameplayIndex = index"
            >
              <span><b>{{ gameplay.name || `玩法 ${index + 1}` }}</b><small>{{ unitText(gameplay) }}</small></span>
              <el-tag size="small" :type="gameplay.status ? 'success' : 'info'">{{ gameplay.status ? '启用' : '停用' }}</el-tag>
            </button>
            <el-empty v-if="!form.gameplays.length" description="请先新增玩法" :image-size="70" />
          </aside>

          <main v-if="activeGameplay" class="gameplay-editor">
            <div class="editor-heading">
              <div><span class="index-badge">{{ activeGameplayIndex + 1 }}</span><h2>{{ activeGameplay.name || '未命名玩法' }}</h2></div>
              <el-button type="danger" plain :icon="Delete" @click="deleteGameplay(activeGameplayIndex)">删除玩法</el-button>
            </div>

            <el-form label-position="top">
              <div class="form-grid three">
                <el-form-item label="玩法名称" required><el-input v-model="activeGameplay.name" placeholder="如：航天" /></el-form-item>
                <el-form-item label="服务者性别">
                  <el-select v-model="activeGameplay.gender_limit">
                    <el-option label="不限（不加价）" value="unlimited" />
                    <el-option label="只男（固定）" value="male_only" />
                    <el-option label="只女（固定）" value="female_only" />
                    <el-option label="性别可选（可加价）" value="optional" />
                  </el-select>
                </el-form-item>
                <el-form-item label="陪玩类型">
                  <el-select v-model="activeGameplay.companion_mode" @change="normalizePriceRules(activeGameplay)">
                    <el-option label="只允许单陪" value="single" /><el-option label="只允许双陪" value="double" /><el-option label="单陪和双陪" value="both" />
                  </el-select>
                </el-form-item>
              </div>
              <div v-if="activeGameplay.gender_limit === 'optional'" class="form-grid two">
                <el-form-item label="选男加价"><el-input-number v-model="activeGameplay.male_price_delta" :min="0" :precision="2" /></el-form-item>
                <el-form-item label="选女加价"><el-input-number v-model="activeGameplay.female_price_delta" :min="0" :precision="2" /></el-form-item>
              </div>
              <el-form-item label="玩法说明"><el-input v-model="activeGameplay.description" maxlength="500" show-word-limit /></el-form-item>
              <div class="form-grid three">
                <el-form-item label="服务小字描述">
                  <el-input v-model="activeGameplay.service_section_desc" maxlength="200" placeholder="如：选择一项服务内容" show-word-limit />
                </el-form-item>
                <el-form-item label="加购服务小字描述">
                  <el-input v-model="activeGameplay.addon_section_desc" maxlength="200" placeholder="如：选择一项服务后，还可继续选择相关内容" show-word-limit />
                </el-form-item>
                <el-form-item label="更多服务小字描述">
                  <el-input v-model="activeGameplay.more_service_section_desc" maxlength="200" placeholder="如：可按需要多选" show-word-limit />
                </el-form-item>
              </div>

              <div class="form-grid four settlement-box">
                <el-form-item label="结算单位">
                  <el-radio-group v-model="activeGameplay.settlement_unit" @change="normalizeSettlement(activeGameplay)">
                    <el-radio-button label="round">按局</el-radio-button><el-radio-button label="hour">按小时</el-radio-button>
                  </el-radio-group>
                </el-form-item>
                <el-form-item label="最低购买量"><el-input-number v-model="activeGameplay.min_quantity" :min="activeGameplay.settlement_unit === 'hour' ? 0.5 : 1" :step="activeGameplay.settlement_unit === 'hour' ? 0.5 : 1" /></el-form-item>
                <el-form-item label="购买步长"><el-input-number v-model="activeGameplay.quantity_step" :min="activeGameplay.settlement_unit === 'hour' ? 0.5 : 1" :step="activeGameplay.settlement_unit === 'hour' ? 0.5 : 1" /></el-form-item>
                <el-form-item :label="`基础单价（元/${activeGameplay.settlement_unit === 'hour' ? '小时' : '局'}）`"><el-input-number v-model="activeGameplay.base_price" :min="0" :precision="2" /></el-form-item>
              </div>

              <div class="switches-inline">
                <el-checkbox v-model="activeGameplay.difficulty_enabled" @change="toggleDifficulty(activeGameplay)">启用难度选择</el-checkbox>
                <el-checkbox v-model="activeGameplay.remark_required">用户必须填写备注</el-checkbox>
                <el-checkbox v-model="activeGameplay.status">启用该玩法</el-checkbox>
              </div>
            </el-form>

            <OptionEditor
              v-if="activeGameplay.difficulty_enabled"
              title="难度选项"
              subtitle="用户选择玩法后显示，例如机密、绝密"
              :rows="activeGameplay.difficulties"
              @add="addOption(activeGameplay.difficulties)"
              @remove="removeOption(activeGameplay.difficulties, $event)"
            />
            <OptionEditor
              title="等级选项"
              subtitle="该玩法独立的等级，例如大专 Pro、985 Pro"
              :rows="activeGameplay.levels"
              show-description
              @add="addOption(activeGameplay.levels, true)"
              @remove="removeOption(activeGameplay.levels, $event)"
            />
            <OptionEditor
              title="服务选项"
              subtitle="用户最终购买的服务内容，例如技术猛攻单"
              :rows="activeGameplay.services"
              show-description
              @add="addServiceOption(activeGameplay.services)"
              @remove="removeOption(activeGameplay.services, $event)"
            />

            <section class="config-section">
              <div class="section-heading">
                <div><h3>加购服务</h3><p>显示在小程序“加购服务”，可为每个按钮配置小字说明。</p></div>
                <el-button type="primary" plain :icon="Plus" @click="addAddon(activeGameplay.value_added_services)">添加加购服务</el-button>
              </div>
              <el-table :data="activeGameplay.value_added_services" empty-text="暂无加购服务">
                <el-table-column label="名称" min-width="150">
                  <template #default="{ row }"><el-input v-model="row.name" placeholder="如：大坝" /></template>
                </el-table-column>
                <el-table-column label="小字描述" min-width="240">
                  <template #default="{ row }"><el-input v-model="row.description" placeholder="显示在按钮名称下方，如：地图" maxlength="200" /></template>
                </el-table-column>
                <el-table-column label="单价（元）" width="150">
                  <template #default="{ row }"><el-input-number v-model="row.price" :min="0" :precision="2" /></template>
                </el-table-column>
                <el-table-column label="排序" width="110">
                  <template #default="{ row }"><el-input-number v-model="row.sort" :min="0" :precision="0" /></template>
                </el-table-column>
                <el-table-column label="启用" width="80">
                  <template #default="{ row }"><el-switch v-model="row.status" /></template>
                </el-table-column>
                <el-table-column label="操作" width="80">
                  <template #default="{ $index }"><el-button type="danger" link @click="removeOption(activeGameplay.value_added_services, $index)">删除</el-button></template>
                </el-table-column>
                <el-table-column type="expand" width="42">
                  <template #default="{ row }">
                    <div class="nested-editor">
                      <div class="nested-heading">
                        <span>{{ row.name || '该加购服务' }}·更多选项</span>
                        <el-button type="primary" link :icon="Plus" @click="addValueAdded(row.value_added_services)">添加选项</el-button>
                      </div>
                      <el-table :data="row.value_added_services" size="small" empty-text="暂无子选项">
                        <el-table-column label="名称" min-width="140">
                          <template #default="{ row: value }"><el-input v-model="value.name" placeholder="如：普通" /></template>
                        </el-table-column>
                        <el-table-column label="小字描述" min-width="220">
                          <template #default="{ row: value }"><el-input v-model="value.description" placeholder="显示在按钮名称下方，如：难度" maxlength="200" /></template>
                        </el-table-column>
                        <el-table-column label="单价（元）" width="150">
                          <template #default="{ row: value }"><el-input-number v-model="value.price" :min="0" :precision="2" /></template>
                        </el-table-column>
                        <el-table-column label="排序" width="110">
                          <template #default="{ row: value }"><el-input-number v-model="value.sort" :min="0" :precision="0" /></template>
                        </el-table-column>
                        <el-table-column label="启用" width="80">
                          <template #default="{ row: value }"><el-switch v-model="value.status" /></template>
                        </el-table-column>
                        <el-table-column label="操作" width="80">
                          <template #default="{ $index }"><el-button type="danger" link @click="removeOption(row.value_added_services, $index)">删除</el-button></template>
                        </el-table-column>
                      </el-table>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </section>

            <section class="config-section">
              <div class="section-heading">
                <div><h3>更多服务</h3><p>每个服务选项下独立配置，显示在小程序“更多服务”，支持自定义小字描述。</p></div>
              </div>
              <el-empty v-if="!activeGameplay.services.length" description="请先添加服务选项" :image-size="70" />
              <div v-else class="service-value-list">
                <div v-for="service in activeGameplay.services" :key="service._key" class="service-value-card">
                  <div class="nested-heading">
                    <span>{{ service.name || '未命名服务' }}</span>
                    <el-button type="primary" link :icon="Plus" @click="addValueAdded(service.value_added_services)">添加更多服务</el-button>
                  </div>
                  <el-table :data="service.value_added_services" size="small" empty-text="暂无更多服务">
                    <el-table-column label="名称" min-width="140">
                      <template #default="{ row }"><el-input v-model="row.name" placeholder="如：甜甜蜜蜜" /></template>
                    </el-table-column>
                    <el-table-column label="小字描述" min-width="240">
                      <template #default="{ row }"><el-input v-model="row.description" placeholder="显示在按钮名称下方，如：全场甜蜜，腻到你发昏" maxlength="200" /></template>
                    </el-table-column>
                    <el-table-column label="单价（元）" width="150">
                      <template #default="{ row }"><el-input-number v-model="row.price" :min="0" :precision="2" /></template>
                    </el-table-column>
                    <el-table-column label="排序" width="110">
                      <template #default="{ row }"><el-input-number v-model="row.sort" :min="0" :precision="0" /></template>
                    </el-table-column>
                    <el-table-column label="启用" width="80">
                      <template #default="{ row }"><el-switch v-model="row.status" /></template>
                    </el-table-column>
                    <el-table-column label="操作" width="80">
                      <template #default="{ $index }"><el-button type="danger" link @click="removeOption(service.value_added_services, $index)">删除</el-button></template>
                    </el-table-column>
                  </el-table>
                </div>
              </div>
            </section>

            <section class="config-section">
              <div class="section-heading">
                <div><h3>组合价格 SKU</h3><p>留空的维度代表通配；匹配到规则时覆盖基础价与选项加价。</p></div>
                <el-button type="primary" plain :icon="Plus" @click="addPriceRule(activeGameplay)">添加价格规则</el-button>
              </div>
              <el-table :data="activeGameplay.price_rules" empty-text="未配置时使用基础价 + 选项加价">
                <el-table-column v-if="activeGameplay.difficulty_enabled" label="难度" min-width="130">
                  <template #default="{ row }"><el-select v-model="row.difficulty_name" clearable placeholder="全部"><el-option v-for="item in activeGameplay.difficulties" :key="item.name" :label="item.name" :value="item.name" /></el-select></template>
                </el-table-column>
                <el-table-column label="等级" min-width="130">
                  <template #default="{ row }"><el-select v-model="row.level_name" clearable placeholder="全部"><el-option v-for="item in activeGameplay.levels" :key="item.name" :label="item.name" :value="item.name" /></el-select></template>
                </el-table-column>
                <el-table-column label="服务" min-width="150">
                  <template #default="{ row }"><el-select v-model="row.service_name" clearable placeholder="全部"><el-option v-for="item in activeGameplay.services" :key="item.name" :label="item.name" :value="item.name" /></el-select></template>
                </el-table-column>
                <el-table-column label="性别" width="120">
                  <template #default="{ row }"><el-select v-model="row.gender_requirement"><el-option label="不限" value="any" /><el-option label="男" value="male" /><el-option label="女" value="female" /></el-select></template>
                </el-table-column>
                <el-table-column label="类型" width="120">
                  <template #default="{ row }"><el-select v-model="row.companion_type"><el-option v-for="type in companionOptions(activeGameplay)" :key="type.value" :label="type.label" :value="type.value" /></el-select></template>
                </el-table-column>
                <el-table-column label="固定单价" width="160">
                  <template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" /></template>
                </el-table-column>
                <el-table-column label="操作" width="80"><template #default="{ $index }"><el-button type="danger" link @click="activeGameplay.price_rules.splice($index, 1)">删除</el-button></template></el-table-column>
              </el-table>
            </section>
          </main>
          <el-empty v-else class="editor-empty" description="新增一个玩法后开始配置" />
        </div>

        <div v-show="activeStep === 2" class="step-panel preview-layout">
          <div class="validation-card">
            <h2>发布检查</h2>
            <div v-for="item in validationItems" :key="item.label" class="check-row" :class="item.ok ? 'ok' : 'error'">
              <el-icon><CircleCheck v-if="item.ok" /><Warning v-else /></el-icon>
              <span>{{ item.label }}</span><b>{{ item.ok ? '通过' : item.tip }}</b>
            </div>
            <el-alert title="订单创建时会保存技能、玩法、选项、结算方式和价格快照，后台修改不会影响历史订单。" type="info" :closable="false" show-icon />
          </div>

          <div class="phone-preview">
            <div class="phone-top"><span>9:41</span><b>自助下单</b><span>•••</span></div>
            <div class="preview-body">
              <h2>我想找</h2>
              <PreviewGroup label="试音" :items="[trialText[form.trial_mode]]" />
              <PreviewGroup label="技能" :items="[form.name || '未命名技能']" />
              <template v-if="previewGameplay">
                <PreviewGroup label="玩法" :items="form.gameplays.map(item => item.name || '未命名')" :active="previewGameplay.name" />
                <PreviewGroup v-if="previewGameplay.difficulty_enabled" label="难度" :items="previewGameplay.difficulties.map(item => item.name)" />
                <PreviewGroup label="等级" :items="previewGameplay.levels.map(item => item.name)" />
                <PreviewGroup label="服务" :items="previewGameplay.services.map(item => item.name)" />
                <PreviewGroup label="性别" :items="[genderText[previewGameplay.gender_limit]]" />
                <PreviewGroup label="类型" :items="companionOptions(previewGameplay).map(item => item.label)" />
                <div class="quantity-row"><span>数量</span><div>－ <b>{{ previewGameplay.min_quantity }}</b> ＋</div><em>{{ previewGameplay.settlement_unit === 'hour' ? '小时' : '局' }}</em></div>
              </template>
              <div class="preview-note">{{ form.remark_placeholder || '填写服务要求' }}</div>
            </div>
            <div class="preview-submit"><span>预计 ¥{{ previewPrice }}</span><button>立即匹配</button></div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="drawer-footer">
          <el-button @click="drawerVisible = false">取消</el-button>
          <div>
            <el-button v-if="activeStep > 0" @click="activeStep--">上一步</el-button>
            <el-button v-if="activeStep < 2" type="primary" @click="nextStep">下一步</el-button>
            <el-button v-else type="primary" :loading="saving" :disabled="!allValid" @click="saveProject">保存并发布</el-button>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import { ElButton, ElInput, ElInputNumber, ElMessage, ElMessageBox, ElSwitch, ElTable, ElTableColumn } from 'element-plus'
import { CircleCheck, CopyDocument, Delete, Edit, Plus, Refresh, Search, Warning } from '@element-plus/icons-vue'
import { createSkillApi, deleteSkillApi, getSkillListApi, updateSkillApi } from '@/api/employee'

const makeKey = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`
const optionRow = (description = false) => ({ _key: makeKey(), name: '', description: description ? '' : undefined, price_delta: 0, sort: 0, status: true })
const serviceRow = () => ({ ...optionRow(true), value_added_services: [] })
const valueAddedRow = () => ({ _key: makeKey(), name: '', description: '', price: 0, sort: 0, status: true })
const newGameplay = () => ({
  _key: makeKey(), name: '', description: '',
  service_section_desc: '选择服务内容',
  addon_section_desc: '选择一项服务后，还可继续选择相关内容',
  more_service_section_desc: '可按需要多选',
  difficulty_enabled: false,
  gender_limit: 'unlimited', male_price_delta: 0, female_price_delta: 0,
  companion_mode: 'single', settlement_unit: 'hour',
  min_quantity: 0.5, quantity_step: 0.5, base_price: 0, remark_required: false,
  sort: 0, status: true, difficulties: [], levels: [optionRow(true)],
  services: [serviceRow()], value_added_services: [], price_rules: []
})
const emptyForm = () => ({
  name: '', category: '', unit_price: 0, sort: 0, status: true, skill_type: 'primary',
  min_people: 1, description: '', trial_mode: 'optional', order_notice: '',
  remark_placeholder: '选填，不超过30个字，如：来个有实力、沟通积极的陪玩',
  self_service_enabled: true, gameplays: [newGameplay()]
})
const clean = (value) => JSON.parse(JSON.stringify(value, (key, item) => key === '_key' ? undefined : item))
const normalizeRow = (row, description = false) => ({ ...row, _key: makeKey(), description: description ? (row.description || '') : undefined, price_delta: Number(row.price_delta || 0) })
const normalizeValueAdded = row => ({ ...valueAddedRow(), ...row, _key: makeKey(), description: row?.description || '', price: Number(row?.price || 0), sort: Number(row?.sort || 0), status: row?.status !== false })
const normalizeServiceRow = row => ({ ...normalizeRow(row, true), value_added_services: (row?.value_added_services || []).map(normalizeValueAdded) })
const normalizeGameplay = (row) => ({
  ...newGameplay(), ...row,
  gender_limit: ({ male: 'male_only', female: 'female_only' })[row.gender_limit] || row.gender_limit || 'unlimited',
  service_section_desc: row.service_section_desc || '选择服务内容',
  addon_section_desc: row.addon_section_desc || '选择一项服务后，还可继续选择相关内容',
  more_service_section_desc: row.more_service_section_desc || '可按需要多选',
  male_price_delta: Number(row.male_price_delta || 0), female_price_delta: Number(row.female_price_delta || 0),
  _key: makeKey(), min_quantity: Number(row.min_quantity || 0),
  quantity_step: Number(row.quantity_step || 0), base_price: Number(row.base_price || 0),
  difficulties: (row.difficulties || []).map(item => normalizeRow(item)),
  levels: (row.levels || []).map(item => normalizeRow(item, true)),
  services: (row.services || []).map(normalizeServiceRow),
  value_added_services: (row.value_added_services || []).map(item => ({
    ...normalizeValueAdded(item),
    value_added_services: (item.value_added_services || []).map(normalizeValueAdded)
  })),
  price_rules: (row.price_rules || []).map(item => ({ ...item, gender_requirement: item.gender_requirement || 'any', _key: makeKey(), unit_price: Number(item.unit_price || 0) }))
})

const OptionEditor = defineComponent({
  props: { title: String, subtitle: String, rows: Array, showDescription: Boolean },
  emits: ['add', 'remove'],
  setup(props, { emit }) {
    return () => h('section', { class: 'config-section' }, [
      h('div', { class: 'section-heading' }, [h('div', [h('h3', props.title), h('p', props.subtitle)]), h(ElButton, { type: 'primary', plain: true, icon: Plus, onClick: () => emit('add') }, () => '添加选项')]),
      h(ElTable, { data: props.rows, emptyText: '暂无选项' }, () => [
        h(ElTableColumn, { label: '名称', minWidth: 160 }, { default: ({ row }) => h(ElInput, { modelValue: row.name, 'onUpdate:modelValue': value => row.name = value, placeholder: '请输入名称' }) }),
        props.showDescription ? h(ElTableColumn, { label: '说明', minWidth: 220 }, { default: ({ row }) => h(ElInput, { modelValue: row.description, 'onUpdate:modelValue': value => row.description = value, placeholder: '可选说明' }) }) : null,
        h(ElTableColumn, { label: '加价（元）', width: 170 }, { default: ({ row }) => h(ElInputNumber, { modelValue: row.price_delta, 'onUpdate:modelValue': value => row.price_delta = value, min: 0, precision: 2 }) }),
        h(ElTableColumn, { label: '启用', width: 80 }, { default: ({ row }) => h(ElSwitch, { modelValue: row.status, 'onUpdate:modelValue': value => row.status = value }) }),
        h(ElTableColumn, { label: '操作', width: 80 }, { default: ({ $index }) => h(ElButton, { type: 'danger', link: true, onClick: () => emit('remove', $index) }, () => '删除') })
      ])
    ])
  }
})

const PreviewGroup = defineComponent({
  props: { label: String, items: Array, active: String },
  setup(props) { return () => h('div', { class: 'preview-group' }, [h('b', props.label), h('div', props.items.filter(Boolean).map((item, index) => h('span', { class: (!props.active && index === 0) || props.active === item ? 'active' : '' }, item)))]) }
})

const rows = ref([]), loading = ref(false), saving = ref(false), keyword = ref(''), statusFilter = ref('all')
const drawerVisible = ref(false), activeStep = ref(0), activeGameplayIndex = ref(0), editingId = ref(null), formRef = ref(null)
const form = reactive(emptyForm())
const statusOptions = [{ label: '全部', value: 'all' }, { label: '已启用', value: 'enabled' }, { label: '未启用', value: 'disabled' }]
const trialText = { disabled: '不试音', optional: '可选试音', required: '必须试音' }
const genderText = { unlimited: '不限', male_only: '只男', female_only: '只女', optional: '性别可选' }
const filteredRows = computed(() => rows.value.filter(row => {
  const matchesKeyword = !keyword.value || `${row.name}${row.category || ''}`.toLowerCase().includes(keyword.value.toLowerCase())
  const matchesStatus = statusFilter.value === 'all' || (statusFilter.value === 'enabled' ? row.self_service_enabled : !row.self_service_enabled)
  return matchesKeyword && matchesStatus
}))
const enabledCount = computed(() => rows.value.filter(row => row.self_service_enabled).length)
const gameplayCount = computed(() => rows.value.reduce((sum, row) => sum + (row.gameplays?.length || 0), 0))
const priceRuleCount = computed(() => rows.value.reduce((sum, row) => sum + countRules(row), 0))
const activeGameplay = computed(() => form.gameplays[activeGameplayIndex.value] || null)
const previewGameplay = computed(() => form.gameplays.find(item => item.status) || form.gameplays[0])
const countRules = row => (row.gameplays || []).reduce((sum, item) => sum + (item.price_rules?.length || 0), 0)
const unitText = gameplay => `${gameplay.settlement_unit === 'hour' ? '按小时' : '按局'} · ¥${Number(gameplay.base_price || 0).toFixed(2)}`
const companionOptions = gameplay => gameplay.companion_mode === 'both' ? [{ label: '单陪', value: 'single' }, { label: '双陪', value: 'double' }] : [{ label: gameplay.companion_mode === 'double' ? '双陪' : '单陪', value: gameplay.companion_mode }]

const validationItems = computed(() => {
  const gameplayValid = form.gameplays.length > 0 && form.gameplays.every(item => item.name.trim())
  const optionsValid = form.gameplays.every(item => item.levels.some(row => row.name.trim()) && item.services.some(row => row.name.trim()))
  const difficultyValid = form.gameplays.every(item => !item.difficulty_enabled || item.difficulties.some(row => row.name.trim()))
  const settlementValid = form.gameplays.every(item => item.settlement_unit === 'hour' ? item.min_quantity >= 0.5 && item.quantity_step >= 0.5 : Number.isInteger(item.min_quantity) && item.min_quantity >= 1 && Number.isInteger(item.quantity_step))
  const doublePriceValid = form.gameplays.every(item => !['double', 'both'].includes(item.companion_mode) || item.price_rules.some(rule => rule.companion_type === 'double' && Number(rule.unit_price) >= 0))
  return [
    { label: '技能基础信息', ok: Boolean(form.name.trim()), tip: '请填写技能名称' },
    { label: '玩法配置', ok: gameplayValid, tip: '请至少添加一个已命名玩法' },
    { label: '等级与服务', ok: optionsValid, tip: '每个玩法至少一个等级和服务' },
    { label: '难度配置', ok: difficultyValid, tip: '启用难度后必须添加选项' },
    { label: '结算数量', ok: settlementValid, tip: '小时最低0.5，局数必须为整数' },
    { label: '双陪价格', ok: doublePriceValid, tip: '双陪玩法至少配置一条双陪价格' },
  ]
})
const allValid = computed(() => validationItems.value.every(item => item.ok))
const previewPrice = computed(() => {
  const gameplay = previewGameplay.value
  if (!gameplay) return '0.00'
  const rule = gameplay.price_rules.find(item => item.companion_type === companionOptions(gameplay)[0].value)
  const optionsDelta = [gameplay.difficulties?.[0], gameplay.levels?.[0], gameplay.services?.[0]].reduce((sum, item) => sum + Number(item?.price_delta || 0), 0)
  return ((rule ? Number(rule.unit_price) : Number(gameplay.base_price || 0) + optionsDelta) * Number(gameplay.min_quantity || 1)).toFixed(2)
})

const loadData = async () => {
  loading.value = true
  try { const res = await getSkillListApi(); rows.value = res.data?.results || [] }
  finally { loading.value = false }
}
const resetForm = data => {
  const normalized = { ...emptyForm(), ...data, gameplays: (data?.gameplays || [newGameplay()]).map(normalizeGameplay) }
  Object.keys(form).forEach(key => delete form[key]); Object.assign(form, normalized)
  activeGameplayIndex.value = 0; activeStep.value = 0
}
const openCreate = () => { editingId.value = null; resetForm(); drawerVisible.value = true }
const openEdit = row => { editingId.value = row.id; resetForm(row); drawerVisible.value = true }
const copyProject = row => { editingId.value = null; resetForm({ ...clean(row), id: undefined, name: `${row.name} 副本`, status: false }); drawerVisible.value = true }
const removeProject = async row => {
  await ElMessageBox.confirm(`删除“${row.name}”后将无法恢复配置，是否继续？`, '删除项目', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  await deleteSkillApi(row.id); ElMessage.success('已删除'); loadData()
}
const addGameplay = () => { form.gameplays.push(newGameplay()); activeGameplayIndex.value = form.gameplays.length - 1 }
const deleteGameplay = async index => {
  await ElMessageBox.confirm('确定删除该玩法及其全部价格配置吗？', '删除玩法', { type: 'warning' })
  form.gameplays.splice(index, 1); activeGameplayIndex.value = Math.max(0, Math.min(index, form.gameplays.length - 1))
}
const addOption = (rows, description = false) => rows.push(optionRow(description))
const addServiceOption = rows => rows.push(serviceRow())
const addAddon = rows => rows.push({ ...valueAddedRow(), value_added_services: [] })
const addValueAdded = rows => rows.push(valueAddedRow())
const removeOption = (rows, index) => rows.splice(index, 1)
const toggleDifficulty = gameplay => { if (!gameplay.difficulty_enabled) { gameplay.difficulties = []; gameplay.price_rules.forEach(item => item.difficulty_name = '') } else if (!gameplay.difficulties.length) gameplay.difficulties.push(optionRow()) }
const normalizeSettlement = gameplay => { if (gameplay.settlement_unit === 'hour') { gameplay.min_quantity = Math.max(0.5, Number(gameplay.min_quantity || 0.5)); gameplay.quantity_step = 0.5 } else { gameplay.min_quantity = Math.max(1, Math.ceil(Number(gameplay.min_quantity || 1))); gameplay.quantity_step = 1 } }
const normalizePriceRules = gameplay => { if (gameplay.companion_mode !== 'both') gameplay.price_rules.forEach(item => item.companion_type = gameplay.companion_mode) }
const addPriceRule = gameplay => gameplay.price_rules.push({ _key: makeKey(), difficulty_name: '', level_name: '', service_name: '', gender_requirement: 'any', companion_type: companionOptions(gameplay)[0].value, unit_price: Number(gameplay.base_price || 0), status: true })
const nextStep = () => { if (activeStep.value === 0 && !form.name.trim()) return ElMessage.warning('请先填写技能名称'); activeStep.value++ }
const saveProject = async () => {
  if (!allValid.value) return ElMessage.warning('请先处理发布检查中的未通过项')
  saving.value = true
  try {
    const payload = clean(form)
    if (editingId.value) await updateSkillApi(editingId.value, payload); else await createSkillApi(payload)
    ElMessage.success(editingId.value ? '项目配置已更新' : '项目已创建')
    drawerVisible.value = false; await loadData()
  } finally { saving.value = false }
}

onMounted(loadData)
</script>

<style scoped>
.self-service-page { min-height: 100%; color: #172033; }
.hero-panel { display: flex; align-items: center; justify-content: space-between; padding: 30px 34px; margin-bottom: 18px; border-radius: 18px; color: white; background: radial-gradient(circle at 82% 0%, rgba(119, 231, 201, .35), transparent 34%), linear-gradient(120deg, #17294b, #234c6c 58%, #21796d); box-shadow: 0 18px 48px rgba(26, 55, 82, .18); }
.hero-panel h1 { margin: 4px 0 8px; font-size: 28px; letter-spacing: .02em; }.hero-panel p { margin: 0; color: rgba(255,255,255,.72); }.eyebrow { font-size: 11px; letter-spacing: .18em; color: #7fe4cb; }
.metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 18px; }.metric-card { padding: 18px 20px; border: 1px solid #e6ebf2; border-radius: 14px; background: #fff; }.metric-card span,.metric-card small { display: block; color: #7b8495; }.metric-card strong { display: block; margin: 8px 0 4px; font-size: 28px; }.metric-card.accent { background: #eaf9f4; border-color: #c9eee1; }
.catalog-card { border-radius: 16px; border: 0; }.toolbar { display: flex; gap: 12px; margin-bottom: 18px; }.search-input { width: 320px; }.skill-cell { display: flex; gap: 12px; align-items: center; }.skill-cell div:last-child { display: flex; flex-direction: column; gap: 4px; }.skill-cell span { color: #8790a1; font-size: 12px; }.skill-avatar { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 12px; color: #176e61; background: #dcf4ed; font-weight: 800; }
.drawer-shell { max-width: 1440px; margin: 0 auto; }.steps { margin: 0 0 26px; padding: 0 10%; }.step-panel { min-height: calc(100vh - 230px); }.basic-panel { max-width: 940px; margin: auto; }.basic-form { padding: 28px; border: 1px solid #e5eaf1; border-radius: 16px; background: #fff; }.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 20px; }.form-grid.three { grid-template-columns: 1.3fr 1fr 1fr; }.form-grid.four { grid-template-columns: repeat(4, minmax(0, 1fr)); }.switch-row { display: flex; align-items: center; justify-content: space-between; padding: 17px 0; border-top: 1px solid #edf0f5; }.switch-row div { display: flex; flex-direction: column; gap: 4px; }.switch-row span { font-size: 12px; color: #9098a8; }
.gameplay-layout { display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 18px; }.gameplay-sidebar { align-self: start; position: sticky; top: 0; padding: 14px; border: 1px solid #e5eaf1; border-radius: 14px; background: #f8fafc; }.side-title { display: flex; justify-content: space-between; align-items: center; padding: 4px 6px 12px; font-weight: 700; }.gameplay-nav { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; padding: 13px 11px; text-align: left; border: 1px solid transparent; border-radius: 10px; background: transparent; cursor: pointer; }.gameplay-nav:hover,.gameplay-nav.active { border-color: #9bd8ca; background: #e8f7f3; }.gameplay-nav span { min-width: 0; display: flex; flex-direction: column; gap: 4px; }.gameplay-nav b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.gameplay-nav small { color: #7d8798; }.gameplay-editor { min-width: 0; }.editor-heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding: 18px 22px; border-radius: 14px; color: white; background: linear-gradient(120deg, #203753, #2d766b); }.editor-heading > div { display: flex; align-items: center; gap: 12px; }.editor-heading h2 { margin: 0; }.index-badge { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 9px; background: rgba(255,255,255,.16); }.settlement-box { padding: 16px 18px 0; border-radius: 12px; background: #f5f8fb; }.switches-inline { display: flex; gap: 28px; margin: 4px 0 18px; }.config-section { margin-top: 14px; padding: 18px; border: 1px solid #e5eaf1; border-radius: 14px; background: #fff; }.section-heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }.section-heading h3 { margin: 0 0 4px; }.section-heading p { margin: 0; color: #8a93a3; font-size: 12px; }.editor-empty { border: 1px dashed #d9dfe8; border-radius: 14px; }
.nested-editor { padding: 8px 14px 16px 46px; background: #f8fafc; }
.nested-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; font-weight: 700; color: #243047; }
.service-value-list { display: grid; gap: 14px; }
.service-value-card { padding: 14px; border: 1px solid #edf0f5; border-radius: 12px; background: #fbfcfe; }
.preview-layout { display: grid; grid-template-columns: minmax(420px, 1fr) 390px; gap: 50px; max-width: 1050px; margin: 0 auto; }.validation-card { align-self: start; padding: 28px; border-radius: 16px; background: white; border: 1px solid #e5eaf1; }.validation-card h2 { margin-top: 0; }.check-row { display: grid; grid-template-columns: 24px 1fr auto; gap: 10px; align-items: center; padding: 14px 0; border-bottom: 1px solid #edf0f4; }.check-row.ok { color: #1c806b; }.check-row.error { color: #d95050; }.check-row b { font-size: 12px; }.validation-card .el-alert { margin-top: 20px; }.phone-preview { height: 700px; display: flex; flex-direction: column; overflow: hidden; border: 10px solid #172033; border-radius: 36px; background: #f7f8fb; box-shadow: 0 24px 60px rgba(25, 39, 59, .22); }.phone-top { display: flex; justify-content: space-between; padding: 20px 18px 14px; background: white; }.preview-body { flex: 1; overflow: auto; padding: 16px; }.preview-body h2 { margin: 0 0 18px; }.preview-group { display: grid; grid-template-columns: 58px 1fr; gap: 8px; margin-bottom: 15px; }.preview-group > div { display: flex; flex-wrap: wrap; gap: 7px; }.preview-group span { padding: 7px 12px; border-radius: 16px; background: #eff1f5; color: #8e96a5; font-size: 12px; }.preview-group span.active { background: #eae5ff; color: #6542c5; }.quantity-row { display: flex; align-items: center; gap: 12px; margin: 18px 0; }.quantity-row > span { width: 46px; font-weight: 700; }.quantity-row div { padding: 6px 12px; border-radius: 16px; background: #eef0f4; }.quantity-row em { font-style: normal; }.preview-note { min-height: 70px; padding: 12px; border-radius: 10px; color: #a0a6b1; background: #eef0f4; }.preview-submit { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px 18px; background: white; }.preview-submit span { color: #eb714c; font-weight: 800; }.preview-submit button { padding: 12px 28px; border: 0; border-radius: 22px; color: white; background: linear-gradient(100deg,#7553e8,#8a49d9); font-weight: 700; }.drawer-footer { display: flex; justify-content: space-between; width: 100%; }
@media (max-width: 1100px) { .metrics-grid { grid-template-columns: repeat(2, 1fr); }.form-grid.four { grid-template-columns: repeat(2, 1fr); }.preview-layout { grid-template-columns: 1fr; }.phone-preview { width: 380px; margin: auto; } }
@media (max-width: 760px) { .hero-panel { align-items: flex-start; gap: 20px; flex-direction: column; }.metrics-grid { grid-template-columns: 1fr; }.toolbar { flex-wrap: wrap; }.search-input { width: 100%; }.gameplay-layout { grid-template-columns: 1fr; }.gameplay-sidebar { position: static; }.form-grid,.form-grid.three,.form-grid.four { grid-template-columns: 1fr; }.switches-inline { align-items: flex-start; flex-direction: column; gap: 8px; } }
</style>
