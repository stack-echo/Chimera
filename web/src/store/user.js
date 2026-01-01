// src/store/user.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
    // ===========================
    // 1. 基础认证数据 (Auth)
    // ===========================
    const token = ref(localStorage.getItem('token') || '')
    // 用户信息中增加 role 字段： 'user' | 'admin'
    const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || '{}'))

    // ===========================
    // 2. 业务上下文数据 (Context)
    // ===========================
    // 默认进入个人空间 (Org=0, KB=1)
    const currentOrgId = ref(parseInt(localStorage.getItem('current_org_id') || 0))
    const currentKbId = ref(parseInt(localStorage.getItem('current_kb_id') || 1))
    const currentOrgName = ref(localStorage.getItem('current_org_name') || '个人空间')

    // 模拟：用户可访问的组织列表 (实际项目应从 userInfo 或 API 获取)
    // 这里的权限逻辑：Admin 可以管理所有，User 只能看自己加入的
    const userOrgs = ref([
        { name: '👤 个人空间', org_id: 0, kb_id: 1, role: 'owner' },
        { name: '🏢 研发部', org_id: 101, kb_id: 2, role: 'member' },
        { name: '💰 财务部', org_id: 102, kb_id: 3, role: 'admin' } // 假设用户在财务部是管理员
    ])

    // ===========================
    // 3. 动作 (Actions)
    // ===========================

    // A. 登录动作 (更新 Auth + 重置 Context)
    function login(newToken, newUser) {
        token.value = newToken
        userInfo.value = newUser

        // 持久化
        localStorage.setItem('token', newToken)
        localStorage.setItem('userInfo', JSON.stringify(newUser))
    }

    // B. 登出动作
    function logout() {
        token.value = ''
        userInfo.value = {}
        currentOrgId.value = 0

        localStorage.clear() // 简单粗暴清空所有
        // 或者逐个移除
        // localStorage.removeItem('token') ...
    }

    // C. 切换组织上下文
    function setContext(org) {
        currentOrgId.value = org.org_id
        currentKbId.value = org.kb_id
        currentOrgName.value = org.name

        localStorage.setItem('current_org_id', org.org_id)
        localStorage.setItem('current_kb_id', org.kb_id)
        localStorage.setItem('current_org_name', org.name)
    }

    // ===========================
    // 4. 计算属性 (Getters)
    // ===========================
    // 判断当前是否是平台超级管理员 (举例)
    const isPlatformAdmin = computed(() => userInfo.value.role === 'admin')

    return {
        token,
        userInfo,
        currentOrgId,
        currentKbId,
        currentOrgName,
        userOrgs,
        isPlatformAdmin,
        login,
        logout,
        setContext
    }
})