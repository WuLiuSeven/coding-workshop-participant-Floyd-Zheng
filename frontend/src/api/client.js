import axios from 'axios';

const apiClient = axios.create({
    //baseURL: 'http://127.0.0.1:8000', //lambda url
    baseURL: import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL}/api/acme`
    : 'http://127.0.0.1:8000',
});



apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('ACMEToken');
    if (token){
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export default apiClient;
