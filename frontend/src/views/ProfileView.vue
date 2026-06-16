<template>
  <div class="page-content">
    <van-nav-bar title="👤 我的" fixed placeholder />

    <div class="profile-page">
      <!-- 用户信息卡 -->
      <van-cell-group inset style="margin-top: 12px;">
        <van-cell title="用户ID" :value="userId" size="small" />
      </van-cell-group>

      <!-- 偏好设置 -->
      <van-cell-group inset title="🎯 租房偏好" style="margin-top: 12px;">
        <van-field v-model="profile.city" label="城市" placeholder="北京" @blur="saveProfile('city', profile.city)" />
        <van-field v-model="profile.budget" label="预算" placeholder="3000" suffix="元/月" @blur="saveProfile('budget', profile.budget)" />
        <van-field label="租房类型">
          <template #input>
            <van-radio-group v-model="profile.rentType" direction="horizontal" @change="saveProfile('rentType', profile.rentType)">
              <van-radio name="整租">整租</van-radio>
              <van-radio name="合租">合租</van-radio>
              <van-radio name="不限">不限</van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <van-field v-model="profile.commute" label="通勤要求" placeholder="30分钟内" @blur="saveProfile('commute', profile.commute)" />
        <van-field label="养宠物">
          <template #input>
            <van-switch v-model="profile.hasPet" size="20px" @change="saveProfile('hasPet', profile.hasPet ? '是' : '否')" />
          </template>
        </van-field>
      </van-cell-group>

      <!-- 我的记录 -->
      <van-cell-group inset title="📂 我的记录" style="margin-top: 12px;">
        <van-cell title="看房记录" is-link to="/checklist" value="查看" />
        <van-cell title="合同审查" is-link to="/contract" value="查看" />
      </van-cell-group>

      <!-- 黑名单 -->
      <van-cell-group inset title="🛡️ 黑名单" style="margin-top: 12px;">
        <van-field v-model="blacklistQuery" label="查询" placeholder="中介/房东名称">
          <template #button>
            <van-button size="small" type="primary" @click="searchBlacklist">查询</van-button>
          </template>
        </van-field>

        <div v-if="blacklistResults.length > 0" class="blacklist-results">
          <van-cell
            v-for="(item, idx) in blacklistResults"
            :key="idx"
            :title="item.name"
            :label="item.reason"
          >
            <template #right-icon>
              <van-tag type="danger">{{ item.type }}</van-tag>
            </template>
          </van-cell>
        </div>

        <van-button plain block size="small" @click="showReportPopup = true" style="margin: 8px 16px;">
          📢 上报黑中介/黑房东
        </van-button>
      </van-cell-group>

      <!-- 关于 -->
      <van-cell-group inset title="ℹ️ 关于" style="margin-top: 12px;">
        <van-cell title="版本" value="v0.1.0" />
        <van-cell title="技术栈" value="Vue3 + Vant4 + FastAPI" />
      </van-cell-group>
    </div>

    <!-- 上报弹窗 -->
    <van-popup v-model:show="showReportPopup" round position="bottom" :style="{ maxHeight: '80%' }">
      <div class="report-popup">
        <h3>📢 上报黑名单</h3>
        <van-field v-model="reportForm.name" label="名称" placeholder="中介/房东名称" />
        <van-field v-model="reportForm.type" label="类型" readonly clickable @click="showTypePicker = true" />
        <van-field v-model="reportForm.reason" label="原因" type="textarea" rows="3" placeholder="描述踩坑经历..." />
        <van-field v-model="reportForm.city" label="城市" placeholder="北京" />
        <van-button type="danger" block round @click="submitReport" style="margin-top: 12px;">
          匿名提交
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showTypePicker" round position="bottom">
      <van-picker :columns="['中介', '房东', '二房东']" @confirm="onTypePick" @cancel="showTypePicker = false" />
    </van-popup>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { showToast } from 'vant'
import { getProfile, updateProfile, checkBlacklist, reportBlacklist } from '../utils/api'

const userId = ref(localStorage.getItem('rentbuddy_user_id') || 'unknown')

const profile = reactive({
  city: '',
  budget: '',
  rentType: '不限',
  commute: '',
  hasPet: false,
})

const blacklistQuery = ref('')
const blacklistResults = ref([])
const showReportPopup = ref(false)
const showTypePicker = ref(false)
const reportForm = reactive({
  name: '',
  type: '中介',
  reason: '',
  city: '北京',
})

onMounted(async () => {
  try {
    const res = await getProfile()
    if (res.profiles) {
      if (res.profiles.city) profile.city = res.profiles.city
      if (res.profiles.budget) profile.budget = res.profiles.budget
      if (res.profiles.rentType) profile.rentType = res.profiles.rentType
      if (res.profiles.commute) profile.commute = res.profiles.commute
      if (res.profiles.hasPet === '是') profile.hasPet = true
    }
  } catch {
    // 首次访问，无偏好数据
  }
})

async function saveProfile(key, value) {
  try {
    await updateProfile(key, String(value))
  } catch {
    // 静默失败
  }
}

async function searchBlacklist() {
  if (!blacklistQuery.value.trim()) return
  try {
    const res = await checkBlacklist(blacklistQuery.value, profile.city || undefined)
    blacklistResults.value = res.results || []
    if (blacklistResults.value.length === 0) {
      showToast('未找到相关记录')
    }
  } catch {
    showToast('查询失败')
  }
}

async function submitReport() {
  if (!reportForm.name || !reportForm.reason) {
    showToast('请填写名称和原因')
    return
  }
  try {
    await reportBlacklist(reportForm)
    showToast('感谢反馈！')
    showReportPopup.value = false
    reportForm.name = ''
    reportForm.reason = ''
  } catch {
    showToast('提交失败')
  }
}

function onTypePick({ selectedValues }) {
  reportForm.type = selectedValues[0]
  showTypePicker.value = false
}
</script>

<style scoped>
.profile-page {
  padding-bottom: 20px;
}
.blacklist-results {
  padding: 0 16px;
}
.report-popup {
  padding: 20px 16px;
}
.report-popup h3 {
  text-align: center;
  margin-bottom: 16px;
}
</style>
