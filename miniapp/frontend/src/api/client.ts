import axios, { type AxiosInstance, type AxiosError } from 'axios';

// Базовый URL API (в production берём из переменных окружения)
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Функция для получения initData из Telegram
function getInitData(): string {
  return window.Telegram?.WebApp?.initData || '';
}

// Создаём axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - добавляем initData в заголовки
apiClient.interceptors.request.use(
  (config) => {
    const initData = getInitData();
    if (initData) {
      config.headers['X-Telegram-Init-Data'] = initData;
    }

    // Для разработки: добавляем dev user id
    if (import.meta.env.DEV && !initData) {
      const devUserId = import.meta.env.VITE_DEV_USER_ID;
      if (devUserId) {
        config.headers['X-Dev-User-Id'] = devUserId;
      }
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - обработка ошибок
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      // Сервер ответил с ошибкой
      const status = error.response.status;
      const data = error.response.data as { detail?: string };

      if (status === 401) {
        console.error('Unauthorized: Invalid Telegram init data');
      } else if (status === 404) {
        console.error('Resource not found');
      } else if (status >= 500) {
        console.error('Server error');
      }

      // Добавляем сообщение об ошибке
      const message = data?.detail || 'Произошла ошибка';
      return Promise.reject(new Error(message));
    } else if (error.request) {
      // Запрос был отправлен, но ответа не было
      return Promise.reject(new Error('Нет связи с сервером'));
    } else {
      // Ошибка при настройке запроса
      return Promise.reject(error);
    }
  }
);

export default apiClient;
