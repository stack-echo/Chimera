import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import ChatHome from '../views/Home.vue' // 原来的 Home 改名为 ChatHome
import AdminDashboard from '../views/AdminDashboard.vue' // 新建管理员页面
import Register from '../views/Register.vue'
import Insights from '../views/Insights.vue'

const routes = [
    { path: '/login', component: Login },
    { path: '/register', component: Register },
    {
        path: '/',
        redirect: '/chat' // 默认跳对话
    },
    {
        path: '/chat',
        component: ChatHome,
        meta: { requiresAuth: true }
    },
    {
        path: '/admin',
        component: AdminDashboard,
        meta: { requiresAuth: true, requiresAdmin: true } // 标记需要管理员权限
    },
    {
        path: '/admin/insights',
        component: Insights,
        meta: { requiresAuth: true } // 如果你的后台有鉴权
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

// 简单的路由守卫
router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('token')
    if (to.meta.requiresAuth && !token) {
        next('/login')
    } else {
        next()
    }
})

export default router