import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Chat',
    component: () => import('../views/ChatView.vue'),
    meta: { title: '租房助手', icon: '🏠' },
  },
  {
    path: '/checklist',
    name: 'Checklist',
    component: () => import('../views/ChecklistView.vue'),
    meta: { title: '看房清单', icon: '📋' },
  },
  {
    path: '/contract',
    name: 'Contract',
    component: () => import('../views/ContractView.vue'),
    meta: { title: '合同审查', icon: '📝' },
  },
  {
    path: '/cost',
    name: 'Cost',
    component: () => import('../views/CostView.vue'),
    meta: { title: '费用计算', icon: '💰' },
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/ProfileView.vue'),
    meta: { title: '我的', icon: '👤' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
