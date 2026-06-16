<template>
  <div class="page-content">
    <van-nav-bar title="📋 看房清单" fixed placeholder />

    <!-- 阶段选择 -->
    <van-tabs v-model:active="activePhase" @change="loadChecklist" sticky>
      <van-tab title="看房前" name="看房前" />
      <van-tab title="看房中" name="看房中" />
      <van-tab title="看房后" name="看房后" />
    </van-tabs>

    <!-- 清单内容 -->
    <div class="checklist-body" v-if="checklistItems.length > 0">
      <van-checkbox-group v-model="checkedItems">
        <van-cell-group inset v-for="(group, gIdx) in checklistItems" :key="gIdx" style="margin-bottom: 12px;">
          <van-cell :title="group.title" :border="false" class="group-title" />
          <van-cell
            v-for="(item, iIdx) in group.items"
            :key="`${gIdx}-${iIdx}`"
            :title="item"
            clickable
          >
            <template #right-icon>
              <van-checkbox :name="`${gIdx}-${iIdx}`" />
            </template>
          </van-cell>
        </van-cell-group>
      </van-checkbox-group>
    </div>

    <van-empty v-else description="加载中..." />

    <!-- 保存区域 -->
    <div class="save-section">
      <van-field v-model="address" label="房源地址" placeholder="如：朝阳区XX小区X号楼" />
      <van-field v-model="notes" label="备注" type="textarea" rows="2" placeholder="看房感想..." />
      <van-button type="primary" block round @click="saveViewing" :disabled="!address" style="margin-top: 12px;">
        保存看房记录
      </van-button>
    </div>

    <!-- 问助手浮动按钮 -->
    <div class="float-btn" @click="$router.push('/')">
      💬 有问题问助手
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import { getChecklist, saveViewing as saveViewingApi } from '../utils/api'

const activePhase = ref('看房中')
const checklistItems = ref([])
const checkedItems = ref([])
const address = ref('')
const notes = ref('')

onMounted(() => {
  loadChecklist()
})

async function loadChecklist() {
  try {
    const res = await getChecklist(activePhase.value)
    checklistItems.value = parseChecklist(res.checklist)
  } catch {
    checklistItems.value = []
  }
}

function parseChecklist(text) {
  if (!text) return []
  const groups = []
  const lines = text.split('\n').filter(l => l.trim())
  let currentGroup = null

  for (const line of lines) {
    const trimmed = line.trim().replace(/^[-•*]\s*/, '')
    if (!trimmed) continue

    // 看起来像标题（短、无编号、或不以数字开头）
    if (trimmed.length <= 6 && !/^[\d１-９]/.test(trimmed)) {
      currentGroup = { title: trimmed, items: [] }
      groups.push(currentGroup)
    } else if (currentGroup) {
      currentGroup.items.push(trimmed)
    } else {
      currentGroup = { title: '检查项', items: [] }
      groups.push(currentGroup)
      currentGroup.items.push(trimmed)
    }
  }
  return groups
}

async function saveViewing() {
  if (!address.value) return
  try {
    await saveViewingApi({
      address: address.value,
      notes: notes.value,
      checklist: { phase: activePhase.value, checked: checkedItems.value },
      score: 0,
    })
    showToast('保存成功')
  } catch {
    showToast('保存失败')
  }
}
</script>

<style scoped>
.checklist-body {
  padding: 12px 0;
}
.group-title {
  font-weight: 600;
  color: #323233;
  background: #f7f8fa;
}
.save-section {
  padding: 16px;
  background: #fff;
  margin-top: 12px;
}
.float-btn {
  position: fixed;
  bottom: 60px;
  right: 16px;
  background: #1989fa;
  color: #fff;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 13px;
  box-shadow: 0 2px 8px rgba(25,137,250,0.4);
  z-index: 10;
}
</style>
