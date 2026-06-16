<template>
  <div class="page-content">
    <van-nav-bar title="📝 合同审查" fixed placeholder />

    <div class="contract-page">
      <!-- 输入区 -->
      <van-cell-group inset title="上传合同">
        <van-field
          v-model="contractText"
          type="textarea"
          rows="6"
          placeholder="粘贴合同文本内容到这里..."
          maxlength="5000"
          show-word-limit
        />
      </van-cell-group>

      <div class="action-row">
        <van-button type="primary" block round :loading="reviewing" @click="doReview" :disabled="!contractText.trim()">
          开始审查
        </van-button>
      </div>

      <!-- 审查结果 -->
      <div v-if="result" class="result-section">
        <van-cell-group inset title="📊 审查结果">
          <!-- 风险等级 -->
          <van-cell
            :title="riskLabel"
            :label="riskDesc"
          >
            <template #right-icon>
              <span class="risk-badge" :class="result.risk_level">
                {{ result.risk_level === 'high' ? '🚨' : result.risk_level === 'medium' ? '⚠️' : '✅' }}
              </span>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- AI 深度审查 -->
        <van-cell-group inset title="🤖 AI 审查意见" style="margin-top: 12px;">
          <div class="review-text" v-html="formatText(result.ai_review)"></div>
        </van-cell-group>

        <!-- 本地规则扫描 -->
        <van-cell-group inset title="🔍 规则扫描" style="margin-top: 12px;">
          <div class="review-text" v-html="formatText(result.local_scan)"></div>
        </van-cell-group>

        <!-- 生成话术 -->
        <van-button plain block round style="margin-top: 12px;" @click="generateSpeech">
          🗣️ 生成谈判话术
        </van-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { showToast } from 'vant'
import { reviewContract, getSpeech } from '../utils/api'
import { useRouter } from 'vue-router'

const router = useRouter()
const contractText = ref('')
const reviewing = ref(false)
const result = ref(null)

const riskLabel = computed(() => {
  if (!result.value) return ''
  const map = { high: '高风险', medium: '中风险', low: '低风险' }
  return map[result.value.risk_level] || '未知'
})

const riskDesc = computed(() => {
  if (!result.value) return ''
  const map = {
    high: '合同存在严重不利条款，建议谨慎签约或要求修改',
    medium: '部分条款需注意，建议与房东协商',
    low: '合同条款基本合理，常规注意即可',
  }
  return map[result.value.risk_level] || ''
})

async function doReview() {
  if (!contractText.value.trim()) return
  reviewing.value = true
  result.value = null

  try {
    result.value = await reviewContract(contractText.value)
  } catch {
    showToast('审查失败，请重试')
  } finally {
    reviewing.value = false
  }
}

async function generateSpeech() {
  try {
    const res = await getSpeech('合同谈判')
    showToast({ message: res.speech, duration: 5000 })
  } catch {
    showToast('生成失败')
  }
}

function formatText(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}
</script>

<style scoped>
.contract-page {
  padding: 0 0 16px;
}
.action-row {
  padding: 12px 16px;
}
.result-section {
  padding-bottom: 20px;
}
.review-text {
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.7;
  color: #323233;
}
.risk-badge {
  font-size: 24px;
}
.risk-badge.high { color: #ee0a24; }
.risk-badge.medium { color: #ff976a; }
.risk-badge.low { color: #07c160; }
</style>
