import request from './request'

export function getAppStats(params) {
    return request({
        url: '/stats',
        method: 'get',
        params // { app_id, days }
    })
}

export function getLogList(params) {
    return request({
        url: '/logs',
        method: 'get',
        params // { page, page_size, app_id, status }
    })
}