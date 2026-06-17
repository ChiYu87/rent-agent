<template>
  <div class="page-content chat-page">
    <!-- 顶部栏 -->
    <van-nav-bar title="🏠 租房助手" fixed placeholder>
      <template #right>
        <van-icon name="delete-o" @click="clearChat" />
      </template>
    </van-nav-bar>

    <!-- 消息列表 -->
    <div class="message-list" ref="messageList">
      <!-- 欢迎消息 -->
      <div v-if="messages.length === 0" class="welcome">
        <div class="welcome-icon">🏠</div>
        <h3>你好，我是租房助手</h3>
        <p>租房子遇到问题？问我！</p>
        <div class="quick-actions">
          <van-button size="small" round @click="sendQuick('第一次租房，要注意什么？')">租房新手指南</van-button>
          <van-button size="small" round @click="goContract">帮我审查合同</van-button>
          <van-button size="small" round @click="sendQuick('月租3000真实成本是多少？')">费用计算</van-button>
          <van-button size="small" round @click="sendQuick('看房要检查哪些？')">看房清单</van-button>
        </div>
      </div>

      <!-- 消息气泡 -->
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        :class="['message-bubble', msg.role === 'user' ? 'user' : 'assistant']"
      >
        <div class="avatar">{{ msg.role === 'user' ? '👤' : '🏠' }}</div>
        <div class="bubble">
          <div class="text" v-html="formatMessage(msg.content)"></div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="message-bubble assistant">
        <div class="avatar">🏠</div>
        <div class="bubble">
          <van-loading size="20px">思考中...</van-loading>
        </div>
      </div>
    </div>

    <!-- 输入栏 -->
    <div class="input-bar">
      <van-field
        v-model="inputText"
        placeholder="输入你的问题..."
        rows="1"
        autosize
        type="textarea"
        @keyup.enter.prevent="sendMessage"
      />
      <van-button
        type="primary"
        size="small"
        round
        :disabled="!inputText.trim() || loading"
        @click="sendMessage"
      >
        发送
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { chatStream, chat, newSession } from '../utils/api'

const router = useRouter()

const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const messageList = ref(null)

function scrollToBottom() {
  nextTick(() => {
    if (messageList.value) {
      messageList.value.scrollTop = messageList.value.scrollHeight
    }
  })
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  // 添加助手消息占位
  const assistantMsg = { role: 'assistant', content: '' }
  messages.value.push(assistantMsg)
  const msgIndex = messages.value.length - 1

  try {
    await chatStream(
      text,
      (chunk) => {
        // 流式追加内容
        messages.value[msgIndex].content += chunk
        scrollToBottom()
      },
      () => {
        loading.value = false
      }
    )
  } catch (e) {
    // 流式失败，降级为普通请求
    try {
      const result = await chat(text)
      messages.value[msgIndex].content = result.reply
    } catch {
      messages.value[msgIndex].content = '⚠️ 网络异常，请稍后重试'
    }
    loading.value = false
  }
}

function sendQuick(text) {
  inputText.value = text
  sendMessage()
}

function goContract() {
  router.push('/contract')
}

function clearChat() {
  messages.value = []
  newSession()
}

function formatMessage(text) {
  // 简单的 Markdown 格式化：换行、加粗
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f7f8fa;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  padding-bottom: 70px;
}

/* 欢迎区 */
.welcome {
  text-align: center;
  padding: 40px 20px;
}
.welcome-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.welcome h3 {
  font-size: 18px;
  margin-bottom: 8px;
}
.welcome p {
  color: #969799;
  margin-bottom: 20px;
}
.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

/* 消息气泡 */
.message-bubble {
  display: flex;
  margin-bottom: 14px;
  align-items: flex-start;
}
.message-bubble.user {
  flex-direction: row-reverse;
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.bubble {
  max-width: 75%;
  margin: 0 8px;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
.message-bubble.user .bubble {
  background: #1989fa;
  color: #fff;
  border-top-right-radius: 4px;
}
.message-bubble.assistant .bubble {
  background: #fff;
  color: #323233;
  border-top-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* 输入栏 */
.input-bar {
  position: fixed;
  bottom: 50px;
  left: 0;
  right: 0;
  max-width: 480px;
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px 12px;
  background: #fff;
  border-top: 1px solid #ebedf0;
  z-index: 100;
}
.input-bar .van-field {
  flex: 1;
  background: #f7f8fa;
  border-radius: 20px;
  padding: 6px 14px;
}
</style>
