<template>
  <div class="page-content">
    <van-nav-bar title="合同审查" fixed placeholder />

    <div class="contract-page">
      <!-- 上传区 -->
      <van-cell-group inset>
        <div class="upload-area">
          <van-uploader
            v-model="fileList"
            :max-count="9"
            :after-read="onAfterRead"
            multiple
            capture="camera"
            upload-text="拍照上传"
          />
          <div class="upload-hint">支持最多9张图片</div>
        </div>
      </van-cell-group>

      <!-- 分隔线 -->
      <div class="divider">
        <span class="divider-text">或粘贴文本</span>
      </div>

      <!-- 文本粘贴 -->
      <van-cell-group inset>
        <van-field
          v-model="contractText"
          type="textarea"
          rows="5"
          placeholder="粘贴合同文本内容到这里..."
          maxlength="10000"
          show-word-limit
        />
      </van-cell-group>

      <!-- 审查按钮 -->
      <div class="action-row">
        <van-button
          type="primary"
          block
          round
          :loading="reviewing"
          :disabled="!canReview"
          @click="doReview"
        >
          开始审查
        </van-button>
      </div>

      <!-- 审查报告 -->
      <div v-if="result" class="result-section">
        <div class="section-divider">
          <span>审查报告</span>
        </div>

        <!-- 评分区 -->
        <div class="score-card" :class="scoreColorClass">
          <div class="score-number">{{ result.score }}</div>
          <div class="score-unit">分</div>
          <div class="score-level">{{ result.level }}</div>
          <div class="score-stats">
            {{ highCount }}高风险 · {{ midCount }}中风险 · {{ missingCount }}缺失
          </div>
          <!-- 圆环装饰 -->
          <svg class="score-ring" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="54" fill="none" stroke="#ebedf0" stroke-width="6" />
            <circle
              cx="60" cy="60" r="54" fill="none"
              :stroke="ringColor"
              stroke-width="6"
              stroke-linecap="round"
              :stroke-dasharray="ringDash"
              transform="rotate(-90 60 60)"
            />
          </svg>
        </div>

        <!-- 合同概要 -->
        <van-cell-group v-if="result.contract_summary" inset title="合同概要" style="margin-top: 12px;">
          <van-cell
            v-if="result.contract_summary.landlord"
            title="房东"
            :value="result.contract_summary.landlord"
          />
          <van-cell
            v-if="result.contract_summary.address"
            title="地址"
            :value="result.contract_summary.address"
          />
          <van-cell
            v-if="result.contract_summary.rent"
            title="租金"
            :value="formatRent(result.contract_summary.rent)"
          />
          <van-cell
            v-if="result.contract_summary.deposit"
            title="押金"
            :value="formatDeposit(result.contract_summary.deposit)"
          />
          <van-cell
            v-if="result.contract_summary.term"
            title="租期"
            :value="result.contract_summary.term"
          />
          <van-cell
            v-if="result.contract_summary.payment"
            title="付款"
            :value="result.contract_summary.payment"
          />
        </van-cell-group>

        <!-- 标准对比 -->
        <div v-if="comparisonItems.length" class="comparison-section">
          <div class="section-divider comparison-divider">
            <span>标准对比</span>
          </div>
          <van-cell-group inset>
            <div
              v-for="(item, idx) in comparisonItems"
              :key="idx"
              class="comparison-row"
            >
              <span class="comparison-icon">{{ item.icon }}</span>
              <span class="comparison-field">{{ item.field }}</span>
              <span class="comparison-values">
                <span class="comparison-standard">标准: {{ item.standard }}</span>
                <span class="comparison-actual">实际: {{ item.actual }}</span>
              </span>
            </div>
          </van-cell-group>
        </div>

        <!-- AI 深度审查 -->
        <div v-if="result.ai_review" class="ai-review-section">
          <div class="section-divider ai-review-divider">
            <span>AI 深度审查</span>
          </div>
          <div class="ai-review-card">
            <div v-if="result.ai_review.summary" class="ai-review-block">
              <div class="ai-review-label">综合摘要</div>
              <div class="ai-review-text">{{ result.ai_review.summary }}</div>
            </div>
            <div v-if="result.ai_review.key_risks && result.ai_review.key_risks.length" class="ai-review-block">
              <div class="ai-review-label">关键风险</div>
              <div
                v-for="(kr, ki) in result.ai_review.key_risks"
                :key="ki"
                class="ai-review-risk-item"
              >
                <span class="ai-review-risk-dot">●</span>
                <span>{{ kr }}</span>
              </div>
            </div>
            <div v-if="result.ai_review.suggestion" class="ai-review-block">
              <div class="ai-review-label">整体建议</div>
              <div class="ai-review-text">{{ result.ai_review.suggestion }}</div>
            </div>
          </div>
        </div>

        <!-- 高风险 -->
        <div v-if="highRisks.length" class="risk-section">
          <div class="section-divider risk-high">
            <span>高风险 ({{ highRisks.length }})</span>
          </div>
          <van-cell-group inset>
            <div
              v-for="risk in highRisks"
              :key="risk.id"
              class="risk-card risk-high"
            >
              <div class="risk-header" @click="toggleRisk(risk.id)">
                <span class="risk-id">{{ risk.id }}</span>
                <span class="risk-title">{{ risk.title }}</span>
                <van-icon :name="expandedRisks[risk.id] ? 'arrow-up' : 'arrow-down'" />
              </div>
              <div v-if="expandedRisks[risk.id]" class="risk-body">
                <div v-if="risk.original_text" class="risk-row">
                  <span class="risk-label">原文:</span>
                  <span class="risk-value risk-original">{{ risk.original_text }}</span>
                </div>
                <div v-if="risk.analysis" class="risk-row">
                  <span class="risk-label">分析:</span>
                  <span class="risk-value">{{ risk.analysis }}</span>
                </div>
                <div v-if="risk.suggestion" class="risk-row">
                  <span class="risk-label">建议:</span>
                  <span class="risk-value risk-suggest">{{ risk.suggestion }}</span>
                </div>
                <div v-if="risk.legal_basis" class="risk-row">
                  <span class="risk-label">法律依据:</span>
                  <span class="risk-value">{{ risk.legal_basis }}</span>
                </div>
                <!-- 谈判话术按钮 -->
                <div class="risk-speech-row">
                  <van-button
                    size="mini"
                    plain
                    round
                    type="primary"
                    :loading="speechLoadingMap[risk.id]"
                    @click.stop="generateRiskSpeech(risk)"
                  >
                    生成话术
                  </van-button>
                </div>
                <!-- 话术结果 -->
                <div v-if="riskSpeechMap[risk.id]" class="risk-speech-result">
                  <div
                    v-for="(sp, si) in riskSpeechMap[risk.id]"
                    :key="si"
                    class="speech-item"
                  >
                    <div class="speech-item-header">
                      <van-tag
                        :type="speechTagType(sp.tone)"
                        size="medium"
                        class="speech-tone-tag"
                      >
                        {{ sp.tone || '建议' }}
                      </van-tag>
                      <van-button
                        size="mini"
                        plain
                        round
                        @click.stop="copyText(sp.content)"
                      >
                        复制
                      </van-button>
                    </div>
                    <div class="speech-item-content">{{ sp.content }}</div>
                  </div>
                </div>
              </div>
            </div>
          </van-cell-group>
        </div>

        <!-- 中风险 -->
        <div v-if="midRisks.length" class="risk-section">
          <div class="section-divider risk-mid">
            <span>中风险 ({{ midRisks.length }})</span>
          </div>
          <van-cell-group inset>
            <div
              v-for="risk in midRisks"
              :key="risk.id"
              class="risk-card risk-mid"
            >
              <div class="risk-header" @click="toggleRisk(risk.id)">
                <span class="risk-id">{{ risk.id }}</span>
                <span class="risk-title">{{ risk.title }}</span>
                <van-icon :name="expandedRisks[risk.id] ? 'arrow-up' : 'arrow-down'" />
              </div>
              <div v-if="expandedRisks[risk.id]" class="risk-body">
                <div v-if="risk.original_text" class="risk-row">
                  <span class="risk-label">原文:</span>
                  <span class="risk-value risk-original">{{ risk.original_text }}</span>
                </div>
                <div v-if="risk.analysis" class="risk-row">
                  <span class="risk-label">分析:</span>
                  <span class="risk-value">{{ risk.analysis }}</span>
                </div>
                <div v-if="risk.suggestion" class="risk-row">
                  <span class="risk-label">建议:</span>
                  <span class="risk-value risk-suggest">{{ risk.suggestion }}</span>
                </div>
                <div v-if="risk.legal_basis" class="risk-row">
                  <span class="risk-label">法律依据:</span>
                  <span class="risk-value">{{ risk.legal_basis }}</span>
                </div>
                <!-- 谈判话术按钮 -->
                <div class="risk-speech-row">
                  <van-button
                    size="mini"
                    plain
                    round
                    type="primary"
                    :loading="speechLoadingMap[risk.id]"
                    @click.stop="generateRiskSpeech(risk)"
                  >
                    生成话术
                  </van-button>
                </div>
                <!-- 话术结果 -->
                <div v-if="riskSpeechMap[risk.id]" class="risk-speech-result">
                  <div
                    v-for="(sp, si) in riskSpeechMap[risk.id]"
                    :key="si"
                    class="speech-item"
                  >
                    <div class="speech-item-header">
                      <van-tag
                        :type="speechTagType(sp.tone)"
                        size="medium"
                        class="speech-tone-tag"
                      >
                        {{ sp.tone || '建议' }}
                      </van-tag>
                      <van-button
                        size="mini"
                        plain
                        round
                        @click.stop="copyText(sp.content)"
                      >
                        复制
                      </van-button>
                    </div>
                    <div class="speech-item-content">{{ sp.content }}</div>
                  </div>
                </div>
              </div>
            </div>
          </van-cell-group>
        </div>

        <!-- 缺失条款 -->
        <div v-if="result.missing && result.missing.length" class="risk-section">
          <div class="section-divider risk-missing">
            <span>缺失条款 ({{ result.missing.length }})</span>
          </div>
          <div class="missing-tags">
            <van-tag
              v-for="item in result.missing"
              :key="item.field"
              :type="item.importance === 'high' ? 'danger' : 'warning'"
              size="large"
              class="missing-tag"
              @click="showMissingDetail(item)"
            >
              {{ item.field }}
            </van-tag>
          </div>
        </div>

        <!-- 底部操作 -->
        <div class="bottom-actions">
          <van-button
            plain
            block
            round
            icon="chat-o"
            @click="generateSpeech"
            :loading="speechLoading"
          >
            生成谈判话术
          </van-button>
          <van-button
            plain
            block
            round
            icon="down"
            @click="saveReport"
            style="margin-top: 8px;"
          >
            保存报告
          </van-button>
        </div>
      </div>
    </div>

    <!-- 谈判话术弹窗 -->
    <van-dialog
      v-model:show="speechDialogVisible"
      title="谈判话术"
      :show-confirm-button="true"
      confirm-button-text="复制"
      @confirm="copySpeech"
    >
      <div class="speech-content">{{ speechText }}</div>
    </van-dialog>

    <!-- 缺失条款详情弹窗 -->
    <van-dialog
      v-model:show="missingDialogVisible"
      :title="missingDetailTitle"
      :show-confirm-button="true"
      confirm-button-text="知道了"
    >
      <div class="speech-content">{{ missingDetailText }}</div>
    </van-dialog>
  </div>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'
import { showToast } from 'vant'
import { reviewContractImages, reviewContractText, getSpeech, getNegotiationSpeech } from '../utils/api'

// ---- 标准合同数据（前端内嵌，用于对比） ----
const STANDARD_CONTRACT = {
  "押金": { "标准": "不超过1个月租金", "上限": "1个月租金" },
  "付款方式": { "标准": "押一付一 或 押一付三", "上限": "押一付三" },
  "中介费": { "标准": "半个月到1个月租金", "上限": "1个月租金" },
  "违约金": { "标准": "不超过1个月租金", "上限": "1个月租金" },
  "维修责任": { "标准": "自然损耗由房东承担" },
  "转租": { "标准": "经房东书面同意可转租" },
  "水电费": { "标准": "按民用标准收费" },
  "提前退租": { "标准": "提前30天书面通知" },
  "租期": { "标准": "常见1年，可续签" },
  "续租优先权": { "标准": "同等条件下租客优先" },
  "房屋用途": { "标准": "仅限居住使用" },
  "入住查验": { "标准": "入住前双方共同查验并签署验收记录" },
  "家具清单": { "标准": "列明所有家具家电品牌型号及状态" },
  "钥匙交接": { "标准": "明确钥匙门禁卡数量并签字确认" },
  "装修约定": { "标准": "允许合理装修，退租时按折旧恢复" },
  "押金退还条件": { "标准": "退租后7-15个工作日内退还" },
  "紧急维修": { "标准": "紧急情况24小时内响应" },
  "解约通知期": { "标准": "提前30天书面通知" },
  "房东进入权": { "标准": "房东进入需提前24小时通知并征得同意" }
}

// ---- 状态 ----
const fileList = ref([])
const rawFiles = ref([]) // 原始 File 对象
const contractText = ref('')
const reviewing = ref(false)
const result = ref(null)
const speechLoading = ref(false)
const speechDialogVisible = ref(false)
const speechText = ref('')
const missingDialogVisible = ref(false)
const missingDetailTitle = ref('')
const missingDetailText = ref('')
const expandedRisks = reactive({})
const riskSpeechMap = reactive({})     // { [riskId]: [{ tone, content }] }
const speechLoadingMap = reactive({})  // { [riskId]: boolean }

// ---- 计算 ----
const canReview = computed(() => {
  return rawFiles.value.length > 0 || contractText.value.trim().length > 0
})

const highRisks = computed(() => {
  if (!result.value || !result.value.risks) return []
  return result.value.risks.filter(r => r.level === 'high')
})

const midRisks = computed(() => {
  if (!result.value || !result.value.risks) return []
  return result.value.risks.filter(r => r.level === 'medium')
})

const highCount = computed(() => highRisks.value.length)
const midCount = computed(() => midRisks.value.length)
const missingCount = computed(() => (result.value && result.value.missing) ? result.value.missing.length : 0)

const scoreColorClass = computed(() => {
  if (!result.value) return ''
  const s = result.value.score
  if (s >= 80) return 'score-green'
  if (s >= 60) return 'score-orange'
  if (s >= 40) return 'score-yellow'
  return 'score-red'
})

const ringColor = computed(() => {
  if (!result.value) return '#07c160'
  const s = result.value.score
  if (s >= 80) return '#07c160'
  if (s >= 60) return '#ff976a'
  if (s >= 40) return '#ffd21e'
  return '#ee0a24'
})

const ringDash = computed(() => {
  if (!result.value) return '0 339.292'
  const ratio = Math.min(result.value.score, 100) / 100
  const circumference = 2 * Math.PI * 54
  const filled = ratio * circumference
  return filled.toFixed(2) + ' ' + circumference.toFixed(2)
})

// 标准对比计算
const comparisonItems = computed(() => {
  if (!result.value || !result.value.contract_info) return []
  const info = result.value.contract_info
  const items = []
  for (const [field, standard] of Object.entries(STANDARD_CONTRACT)) {
    const actualVal = info[field] || null
    if (actualVal === null || actualVal === undefined) {
      items.push({ field, standard: standard['标准'], actual: '未约定', icon: '❌' })
    } else if (isCompliant(field, actualVal, standard)) {
      items.push({ field, standard: standard['标准'], actual: String(actualVal), icon: '✅' })
    } else {
      items.push({ field, standard: standard['标准'], actual: String(actualVal), icon: '⚠️' })
    }
  }
  return items
})

// ---- 方法 ----
function isCompliant(field, actual, standard) {
  const actualStr = String(actual).trim()
  const stdStr = standard['标准'] || ''
  // 如果实际值包含标准值的关键字，视为合规
  const stdKeywords = stdStr.replace(/[不超过或及可由常见可续签按并签署列明明确退租时]/g, '').split(/[\s,，、]+/).filter(k => k.length >= 2)
  if (stdKeywords.some(k => actualStr.includes(k))) return true
  // 特殊规则
  if (field === '押金') {
    const match = actualStr.match(/(\d)/)
    if (match && parseInt(match[1]) <= 1) return true
  }
  if (field === '付款方式') {
    if (actualStr.includes('押一付一') || actualStr.includes('押一付三')) return true
  }
  if (field === '违约金' || field === '中介费') {
    const match = actualStr.match(/(\d)/)
    if (match && parseInt(match[1]) <= 1) return true
  }
  return false
}

function toggleRisk(id) {
  expandedRisks[id] = !expandedRisks[id]
}

function onAfterRead(readFile) {
  if (Array.isArray(readFile)) {
    readFile.forEach(f => {
      rawFiles.value.push(f.file)
    })
  } else {
    rawFiles.value.push(readFile.file)
  }
}

async function doReview() {
  reviewing.value = true
  result.value = null
  // 清空话术缓存
  Object.keys(riskSpeechMap).forEach(k => delete riskSpeechMap[k])
  Object.keys(speechLoadingMap).forEach(k => delete speechLoadingMap[k])

  try {
    if (rawFiles.value.length > 0) {
      result.value = await reviewContractImages(rawFiles.value)
    } else if (contractText.value.trim()) {
      result.value = await reviewContractText(contractText.value.trim())
    }
  } catch (e) {
    showToast(e.message || '审查失败，请重试')
  } finally {
    reviewing.value = false
  }
}

// 为单条风险生成谈判话术
async function generateRiskSpeech(risk) {
  if (speechLoadingMap[risk.id]) return
  speechLoadingMap[risk.id] = true
  try {
    const res = await getNegotiationSpeech([risk.id])
    // 后端返回格式: { speeches: [{ risk_id, tone, content }] } 或 { speech: [...] }
    let speeches = res.speeches || res.speech || []
    if (typeof speeches === 'string') {
      speeches = [{ tone: '建议', content: speeches }]
    }
    if (!Array.isArray(speeches)) {
      speeches = [{ tone: '建议', content: String(speeches) }]
    }
    riskSpeechMap[risk.id] = speeches
  } catch {
    showToast('话术生成失败')
  } finally {
    speechLoadingMap[risk.id] = false
  }
}

// 全局谈判话术（保留原有功能）
async function generateSpeech() {
  speechLoading.value = true
  try {
    const res = await getSpeech('合同谈判')
    speechText.value = res.speech || res.reply || JSON.stringify(res)
    speechDialogVisible.value = true
  } catch {
    showToast('生成失败')
  } finally {
    speechLoading.value = false
  }
}

function speechTagType(tone) {
  if (!tone) return 'primary'
  const t = tone.toLowerCase()
  if (t.includes('强硬') || t.includes('firm')) return 'danger'
  if (t.includes('礼貌') || t.includes('polite')) return 'success'
  return 'primary'
}

function copyText(text) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      showToast('已复制')
    }).catch(() => {
      fallbackCopy(text)
    })
  } else {
    fallbackCopy(text)
  }
}

function copySpeech() {
  copyText(speechText.value)
}

function fallbackCopy(text) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  try {
    document.execCommand('copy')
    showToast('已复制')
  } catch {
    showToast('复制失败')
  }
  document.body.removeChild(textarea)
}

function saveReport() {
  if (!result.value) return
  const blob = new Blob([JSON.stringify(result.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const dateStr = new Date().toISOString().slice(0, 10)
  a.download = 'contract_report_' + dateStr + '.json'
  a.click()
  URL.revokeObjectURL(url)
  showToast('报告已保存')
}

function formatRent(val) {
  if (val === null || val === undefined) return ''
  return '\u00A5' + Number(val).toLocaleString() + '/月'
}

function formatDeposit(val) {
  if (val === null || val === undefined) return ''
  return '\u00A5' + Number(val).toLocaleString()
}

function showMissingDetail(item) {
  missingDetailTitle.value = item.field
  missingDetailText.value = item.suggestion || '建议补充此条款以保障权益'
  missingDialogVisible.value = true
}
</script>

<style scoped>
.contract-page {
  padding: 0 0 24px;
  max-width: 480px;
  margin: 0 auto;
}

/* 上传区 */
.upload-area {
  padding: 16px;
  text-align: center;
}
.upload-hint {
  font-size: 12px;
  color: #969799;
  margin-top: 8px;
}

/* 分隔线 */
.divider {
  display: flex;
  align-items: center;
  padding: 12px 24px;
  color: #969799;
  font-size: 13px;
}
.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #ebedf0;
}
.divider-text {
  padding: 0 12px;
}

/* 操作行 */
.action-row {
  padding: 12px 16px;
}

/* 分区标题 */
.section-divider {
  display: flex;
  align-items: center;
  padding: 16px 16px 8px;
  font-size: 15px;
  font-weight: 600;
  color: #323233;
}
.section-divider::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  border-radius: 2px;
  margin-right: 8px;
  background: #1989fa;
}
.section-divider.risk-high::before {
  background: #ee0a24;
}
.section-divider.risk-mid::before {
  background: #ff976a;
}
.section-divider.risk-missing::before {
  background: #969799;
}
.section-divider.comparison-divider::before {
  background: #07c160;
}
.section-divider.ai-review-divider::before {
  background: #1989fa;
}

/* 评分卡片 */
.score-card {
  position: relative;
  margin: 12px 16px;
  padding: 24px 16px;
  border-radius: 16px;
  text-align: center;
  overflow: hidden;
}
.score-card.score-green {
  background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
  color: #2e7d32;
}
.score-card.score-yellow {
  background: linear-gradient(135deg, #fff8e1, #ffecb3);
  color: #f57f17;
}
.score-card.score-orange {
  background: linear-gradient(135deg, #fff3e0, #ffe0b2);
  color: #e65100;
}
.score-card.score-red {
  background: linear-gradient(135deg, #ffebee, #ffcdd2);
  color: #c62828;
}
.score-number {
  font-size: 64px;
  font-weight: 700;
  line-height: 1;
  position: relative;
  z-index: 1;
}
.score-unit {
  font-size: 16px;
  font-weight: 400;
  position: relative;
  z-index: 1;
}
.score-level {
  font-size: 16px;
  font-weight: 600;
  margin-top: 4px;
  position: relative;
  z-index: 1;
}
.score-stats {
  font-size: 13px;
  margin-top: 8px;
  opacity: 0.85;
  position: relative;
  z-index: 1;
}
.score-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 120px;
  height: 120px;
  opacity: 0.15;
}

/* 风险卡片 */
.risk-card {
  padding: 12px 16px;
  border-bottom: 1px solid #f5f5f5;
}
.risk-card:last-child {
  border-bottom: none;
}
.risk-header {
  display: flex;
  align-items: center;
  cursor: pointer;
}
.risk-id {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  margin-right: 8px;
  color: #fff;
}
.risk-high .risk-id {
  background: #ee0a24;
}
.risk-mid .risk-id {
  background: #ff976a;
}
.risk-title {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
}
.risk-body {
  margin-top: 10px;
  padding-left: 56px;
  font-size: 13px;
  line-height: 1.7;
  color: #646566;
}
.risk-row {
  margin-bottom: 6px;
}
.risk-label {
  color: #969799;
  margin-right: 4px;
}
.risk-original {
  color: #323233;
  background: #f7f8fa;
  padding: 2px 6px;
  border-radius: 4px;
}
.risk-suggest {
  color: #07c160;
}

/* 话术行 */
.risk-speech-row {
  margin-top: 8px;
  display: flex;
  align-items: center;
}

/* 话术结果 */
.risk-speech-result {
  margin-top: 8px;
  background: #f7f8fa;
  border-radius: 8px;
  padding: 10px 12px;
}
.speech-item {
  margin-bottom: 10px;
}
.speech-item:last-child {
  margin-bottom: 0;
}
.speech-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.speech-tone-tag {
  flex-shrink: 0;
}
.speech-item-content {
  font-size: 13px;
  line-height: 1.7;
  color: #323233;
  white-space: pre-wrap;
}

/* 标准对比 */
.comparison-section {
  margin-top: 4px;
}
.comparison-row {
  display: flex;
  align-items: flex-start;
  padding: 10px 16px;
  border-bottom: 1px solid #f5f5f5;
  font-size: 13px;
  line-height: 1.5;
}
.comparison-row:last-child {
  border-bottom: none;
}
.comparison-icon {
  flex-shrink: 0;
  width: 24px;
  font-size: 15px;
  text-align: center;
}
.comparison-field {
  flex-shrink: 0;
  width: 80px;
  font-weight: 500;
  color: #323233;
}
.comparison-values {
  flex: 1;
  display: flex;
  flex-direction: column;
  color: #646566;
}
.comparison-standard {
  font-size: 12px;
  color: #969799;
}
.comparison-actual {
  font-size: 13px;
  color: #323233;
  font-weight: 500;
}

/* AI 深度审查 */
.ai-review-section {
  margin-top: 4px;
}
.ai-review-card {
  margin: 0 16px;
  padding: 16px;
  background: linear-gradient(135deg, #e3f2fd, #bbdefb);
  border-radius: 12px;
}
.ai-review-block {
  margin-bottom: 12px;
}
.ai-review-block:last-child {
  margin-bottom: 0;
}
.ai-review-label {
  font-size: 14px;
  font-weight: 600;
  color: #1565c0;
  margin-bottom: 6px;
}
.ai-review-text {
  font-size: 13px;
  line-height: 1.8;
  color: #323233;
  white-space: pre-wrap;
}
.ai-review-risk-item {
  display: flex;
  align-items: flex-start;
  font-size: 13px;
  line-height: 1.7;
  color: #323233;
  margin-bottom: 4px;
}
.ai-review-risk-dot {
  color: #e53935;
  margin-right: 6px;
  flex-shrink: 0;
}

/* 缺失标签 */
.missing-tags {
  padding: 12px 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.missing-tag {
  cursor: pointer;
}

/* 底部操作 */
.bottom-actions {
  padding: 16px 16px 0;
}

/* 话术弹窗 */
.speech-content {
  padding: 16px;
  font-size: 14px;
  line-height: 1.8;
  color: #323233;
  white-space: pre-wrap;
  max-height: 60vh;
  overflow-y: auto;
}

/* 结果区域 */
.result-section {
  padding-bottom: 20px;
}
</style>
