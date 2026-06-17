/**
 * RentBuddy API 客户端
 * 所有请求自动带 user_id，支持 SSE 流式
 */

const API_BASE = '/api'

// 用户 ID：首次访问自动生成，存 localStorage
function getUserId() {
  let id = localStorage.getItem('rentbuddy_user_id')
  if (!id) {
    id = 'u_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
    localStorage.setItem('rentbuddy_user_id', id)
  }
  return id
}

// 会话 ID
let sessionId = null

export function getSessionId() {
  return sessionId
}

export function newSession() {
  sessionId = null
}

// 通用请求
async function request(method, path, data = null, params = null) {
  let url = `${API_BASE}${path}`
  if (params) {
    const qs = new URLSearchParams(params).toString()
    url += `?${qs}`
  }

  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (data) {
    opts.body = JSON.stringify(data)
  }

  const resp = await fetch(url, opts)
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || '请求失败')
  }
  return resp.json()
}

// ==================== 对话 ====================

export async function chat(message) {
  const data = { user_id: getUserId(), message }
  if (sessionId) data.session_id = sessionId

  const result = await request('POST', '/chat', data)
  sessionId = result.session_id
  return result
}

/**
 * SSE 流式对话
 * @param {string} message 用户消息
 * @param {function} onChunk 收到 chunk 回调
 * @param {function} onDone 完成回调
 */
export async function chatStream(message, onChunk, onDone) {
  const data = { user_id: getUserId(), message }
  if (sessionId) data.session_id = sessionId

  const resp = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })

  if (!resp.ok) {
    throw new Error('对话请求失败')
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const payload = line.slice(6).trim()
        if (payload === '[DONE]') {
          onDone && onDone()
          return
        }
        try {
          const parsed = JSON.parse(payload)
          if (parsed.session_id) sessionId = parsed.session_id
          if (parsed.chunk) onChunk(parsed.chunk)
        } catch {
          // 跳过非法 JSON
        }
      }
    }
  }
  onDone && onDone()
}

// ==================== 合同审查 ====================

export async function reviewContract(contractText) {
  return request('POST', '/contract/review', {
    user_id: getUserId(),
    contract_text: contractText,
  })
}

// 合同图片审查（新版结构化）
export async function reviewContractImages(files) {
  const formData = new FormData()
  files.forEach(f => formData.append('files', f))
  const resp = await fetch(`${API_BASE}/contract/review/upload?user_id=${getUserId()}`, {
    method: 'POST',
    body: formData,
  })
  if (!resp.ok) throw new Error('审查失败')
  const data = await resp.json()
  // 兼容新旧字段：ai_review / negotiation_speech 可能不存在
  if (!data.ai_review) data.ai_review = null
  if (!data.negotiation_speech) data.negotiation_speech = null
  return data
}

// 合同文本审查（新版结构化）
export async function reviewContractText(contractText) {
  const data = await request('POST', '/contract/review/text', {
    user_id: getUserId(),
    contract_text: contractText,
  })
  // 兼容新旧字段：ai_review / negotiation_speech 可能不存在
  if (!data.ai_review) data.ai_review = null
  if (!data.negotiation_speech) data.negotiation_speech = null
  return data
}

export async function uploadContract(file) {
  const formData = new FormData()
  formData.append('file', file)

  const resp = await fetch(`${API_BASE}/contract/upload?user_id=${getUserId()}`, {
    method: 'POST',
    body: formData,
  })
  if (!resp.ok) throw new Error('上传失败')
  return resp.json()
}

// 获取谈判话术（按风险 ID）
export async function getNegotiationSpeech(riskIds) {
  const ids = Array.isArray(riskIds) ? riskIds.join(',') : riskIds
  return request('GET', '/contract/negotiation-speech', null, { risk_ids: ids })
}

// AI 深度审查（按需触发，带超时保护）
export async function aiReviewContract(contractText) {
  return request('POST', '/contract/ai-review', {
    user_id: getUserId(),
    contract_text: contractText,
  })
}

export async function getContractList(limit = 10) {
  return request('GET', '/contract/list', null, { user_id: getUserId(), limit })
}

// ==================== 费用计算 ====================

export async function calcCost(params) {
  return request('POST', '/tools/cost', params)
}

export async function calcDeposit(params) {
  return request('POST', '/tools/deposit', params)
}

// ==================== 看房清单 ====================

export async function getChecklist(phase = '看房中') {
  return request('POST', '/tools/checklist', { phase })
}

export async function saveViewing(data) {
  return request('POST', '/tools/viewing/save', {
    user_id: getUserId(),
    ...data,
  })
}

export async function getViewingList(limit = 20) {
  return request('GET', '/tools/viewing/list', null, { user_id: getUserId(), limit })
}

// ==================== 黑名单 ====================

export async function checkBlacklist(name, city = null) {
  return request('POST', '/tools/blacklist/check', { name, city })
}

export async function reportBlacklist(data) {
  return request('POST', '/tools/blacklist/report', {
    user_id: getUserId(),
    ...data,
  })
}

// ==================== 城市 & 话术 ====================

export async function getCityRules(city = '北京') {
  return request('GET', '/tools/city-rules', null, { city })
}

export async function getSpeech(situation = '问价格') {
  return request('GET', '/tools/speech', null, { situation })
}

// ==================== 用户偏好 ====================

export async function getProfile() {
  return request('GET', '/tools/profile', null, { user_id: getUserId() })
}

export async function updateProfile(key, value) {
  return request('POST', '/tools/profile', {
    user_id: getUserId(),
    key,
    value,
  })
}

// ==================== 健康 ====================

export async function healthCheck() {
  return request('GET', '/health')
}

export default {
  chat, chatStream, newSession,
  reviewContract, reviewContractImages, reviewContractText, getNegotiationSpeech, aiReviewContract, uploadContract, getContractList,
  calcCost, calcDeposit,
  getChecklist, saveViewing, getViewingList,
  checkBlacklist, reportBlacklist,
  getCityRules, getSpeech,
  getProfile, updateProfile,
  healthCheck,
}
