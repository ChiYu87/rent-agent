<template>
  <div class="page-content">
    <van-nav-bar title="💰 费用计算" fixed placeholder />

    <div class="cost-page">
      <!-- 输入区 -->
      <van-cell-group inset title="租金信息">
        <van-field v-model="form.rent" label="月租金" type="number" placeholder="3000" suffix="元" />
        <van-field v-model="form.deposit" label="押金" type="number" placeholder="留空=1个月租金" suffix="元" />
        <van-field label="付款方式">
          <template #input>
            <van-radio-group v-model="form.paymentCycle" direction="horizontal">
              <van-radio name="押一付一">押一付一</van-radio>
              <van-radio name="押一付三">押一付三</van-radio>
              <van-radio name="押一付六">押一付六</van-radio>
            </van-radio-group>
          </template>
        </van-field>
      </van-cell-group>

      <van-cell-group inset title="其他费用" style="margin-top: 12px;">
        <van-field v-model="form.agentFee" label="中介费" type="number" placeholder="0" suffix="元" />
        <van-field v-model="form.utilities" label="水电燃网" type="number" placeholder="200" suffix="元/月" />
        <van-field v-model="form.propertyFee" label="物业费" type="number" placeholder="0" suffix="元/月" />
      </van-cell-group>

      <div class="action-row">
        <van-button type="primary" block round @click="calculate">计算真实成本</van-button>
      </div>

      <!-- 计算结果 -->
      <van-cell-group v-if="costResult" inset title="📊 费用明细" style="margin-top: 12px;">
        <van-cell
          v-for="(val, key) in costResult"
          :key="key"
          :title="key"
          :value="val"
        />
      </van-cell-group>

      <!-- 押金模拟 -->
      <van-cell-group inset title="🔒 押金退还不模拟" style="margin-top: 12px;">
        <van-field v-model="depositForm.earlyTermination" label="提前退租" readonly clickable @click="showEarlyPicker = true" />
        <van-field v-model="depositForm.hasDamage" label="有损坏" readonly clickable @click="showDamagePicker = true" />
        <van-button plain block round size="small" @click="calcDeposit" style="margin: 8px 16px;">
          模拟押金退还
        </van-button>
      </van-cell-group>

      <van-cell-group v-if="depositResult" inset style="margin-top: 8px;">
        <van-cell
          v-for="(val, key) in depositResult"
          :key="key"
          :title="key"
          :value="val"
        />
      </van-cell-group>
    </div>

    <!-- 选择器 -->
    <van-popup v-model:show="showEarlyPicker" round position="bottom">
      <van-picker :columns="['否', '是']" @confirm="onEarlyPick" @cancel="showEarlyPicker = false" />
    </van-popup>
    <van-popup v-model:show="showDamagePicker" round position="bottom">
      <van-picker :columns="['不确定', '否', '是']" @confirm="onDamagePick" @cancel="showDamagePicker = false" />
    </van-popup>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { showToast } from 'vant'
import { calcCost, calcDeposit as calcDepositApi } from '../utils/api'

const form = reactive({
  rent: '3000',
  deposit: '',
  paymentCycle: '押一付三',
  agentFee: '1500',
  utilities: '200',
  propertyFee: '0',
})

const costResult = ref(null)

const depositForm = reactive({
  earlyTermination: '否',
  hasDamage: '不确定',
})
const depositResult = ref(null)
const showEarlyPicker = ref(false)
const showDamagePicker = ref(false)

async function calculate() {
  const rent = parseFloat(form.rent)
  if (!rent || rent <= 0) {
    showToast('请输入月租金')
    return
  }

  try {
    const res = await calcCost({
      rent,
      deposit: form.deposit ? parseFloat(form.deposit) : undefined,
      agent_fee: parseFloat(form.agentFee) || 0,
      utilities: parseFloat(form.utilities) || 200,
      property_fee: parseFloat(form.propertyFee) || 0,
      payment_cycle: form.paymentCycle,
    })
    // 解析 JSON 字符串结果
    try {
      costResult.value = typeof res.result === 'string' ? JSON.parse(res.result) : res.result
    } catch {
      costResult.value = { '计算结果': res.result }
    }
  } catch {
    showToast('计算失败')
  }
}

async function calcDeposit() {
  const rent = parseFloat(form.rent)
  const deposit = form.deposit ? parseFloat(form.deposit) : rent
  if (!deposit) return

  try {
    const res = await calcDepositApi({
      deposit,
      contract_months: 12,
      early_termination: depositForm.earlyTermination,
      has_damage: depositForm.hasDamage,
    })
    try {
      depositResult.value = typeof res.result === 'string' ? JSON.parse(res.result) : res.result
    } catch {
      depositResult.value = { '模拟结果': res.result }
    }
  } catch {
    showToast('模拟失败')
  }
}

function onEarlyPick({ selectedValues }) {
  depositForm.earlyTermination = selectedValues[0]
  showEarlyPicker.value = false
}
function onDamagePick({ selectedValues }) {
  depositForm.hasDamage = selectedValues[0]
  showDamagePicker.value = false
}
</script>

<style scoped>
.cost-page {
  padding-bottom: 20px;
}
.action-row {
  padding: 12px 16px;
}
</style>
