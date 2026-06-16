<template>
  <router-view />
  <van-tabbar v-model="active" route>
    <van-tabbar-item to="/" icon="chat-o">助手</van-tabbar-item>
    <van-tabbar-item to="/checklist" icon="todo-list-o">清单</van-tabbar-item>
    <van-tabbar-item to="/contract" icon="description">合同</van-tabbar-item>
    <van-tabbar-item to="/cost" icon="gold-coin-o">费用</van-tabbar-item>
    <van-tabbar-item to="/profile" icon="user-o">我的</van-tabbar-item>
  </van-tabbar>
</template>

<script setup>
import { ref } from 'vue'
const active = ref(0)
</script>

<style>
:root {
  --van-primary-color: #1989fa;
  --van-tabbar-height: 50px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f7f8fa;
  -webkit-font-smoothing: antialiased;
}

#app {
  max-width: 480px;
  margin: 0 auto;
  min-height: 100vh;
  background: #f7f8fa;
  position: relative;
}

/* 页面内容留出 tabbar 空间 */
.page-content {
  padding-bottom: 60px;
  min-height: 100vh;
}
</style>
