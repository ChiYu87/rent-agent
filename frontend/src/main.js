import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// Vant 样式（自动导入组件，但基础样式需要手动引入）
import 'vant/lib/index.css'

const app = createApp(App)
app.use(router)
app.mount('#app')
