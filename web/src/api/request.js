// src/api/request.js
import axios from 'axios'
import { useUserStore } from '../store/user'
import { Message } from '@arco-design/web-vue'

// 创建 axios 实例
const service = axios.create({
    baseURL: 'http://localhost:8080/api/v1', // 后端地址
    timeout: 60000,
})

// request 拦截器
service.interceptors.request.use(
    config => {
        // 从 localStorage 获取 token
        const token = localStorage.getItem('token')
        if (token) {
            // Go 后端通常期望 Authorization: Bearer <token>
            config.headers['Authorization'] = `Bearer ${token}`
        }
        return config
    },
    error => {
        console.log(error)
        return Promise.reject(error)
    }
)

// response 拦截器
service.interceptors.response.use(
    response => {
        const res = response.data
        // 假设 Go 后端返回 { code: 200, data: ..., message: ... }
        // 如果 code 不是 200，视为错误 (根据你的 Go 逻辑调整)
        return res
    },
    error => {
        console.log('err' + error)
        return Promise.reject(error)
    }
)

export default service