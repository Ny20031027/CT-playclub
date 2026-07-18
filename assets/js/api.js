const API_BASE = '/api';

function getToken() {
    return localStorage.getItem('token');
}

function setToken(token) {
    localStorage.setItem('token', token);
}

function removeToken() {
    localStorage.removeItem('token');
    localStorage.removeItem('userInfo');
}

function getUserInfo() {
    try {
        return JSON.parse(localStorage.getItem('userInfo'));
    } catch {
        return null;
    }
}

function setUserInfo(userInfo) {
    localStorage.setItem('userInfo', JSON.stringify(userInfo));
}

async function request(url, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        if (response.status === 401) {
            removeToken();
            window.location.href = '/login/';
        }
        throw new Error(data.msg || '请求失败');
    }
    
    return data;
}

async function get(url, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const fullUrl = queryString ? `${url}?${queryString}` : url;
    return request(fullUrl, { method: 'GET' });
}

async function post(url, data = {}) {
    return request(url, { method: 'POST', body: JSON.stringify(data) });
}

async function put(url, data = {}) {
    return request(url, { method: 'PUT', body: JSON.stringify(data) });
}

async function del(url) {
    return request(url, { method: 'DELETE' });
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function showModal(modalId) {
    document.getElementById(modalId).classList.add('show');
}

function hideModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN');
}

function formatMoney(amount) {
    if (!amount) return '0.00';
    return Number(amount).toFixed(2);
}

function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

function logout() {
    removeToken();
    window.location.href = '/login/';
}

async function checkLogin() {
    const token = getToken();
    if (!token) {
        window.location.href = '/login/';
        return false;
    }
    return true;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

async function upload(url, formData) {
    const token = getToken();
    const headers = {};

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${url}`, {
        method: 'POST',
        headers,
        body: formData
    });

    const data = await response.json();

    if (!response.ok) {
        if (response.status === 401) {
            removeToken();
            window.location.href = '/login/';
        }
        throw new Error(data.msg || '上传失败');
    }

    return data;
}