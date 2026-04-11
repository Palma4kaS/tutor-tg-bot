import { useEffect, useState, useCallback } from 'react';

// Типы Telegram WebApp
interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
}

interface ThemeParams {
  bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  secondary_bg_color?: string;
  header_bg_color?: string;
  accent_text_color?: string;
  section_bg_color?: string;
  section_header_text_color?: string;
  subtitle_text_color?: string;
  destructive_text_color?: string;
}

interface WebApp {
  initData: string;
  initDataUnsafe: {
    user?: TelegramUser;
    auth_date?: number;
    hash?: string;
  };
  version: string;
  platform: string;
  colorScheme: 'light' | 'dark';
  themeParams: ThemeParams;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  headerColor: string;
  backgroundColor: string;

  // Методы
  ready: () => void;
  expand: () => void;
  close: () => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;

  // BackButton
  BackButton: {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
  };

  // MainButton
  MainButton: {
    text: string;
    color: string;
    textColor: string;
    isVisible: boolean;
    isActive: boolean;
    isProgressVisible: boolean;
    setText: (text: string) => void;
    show: () => void;
    hide: () => void;
    enable: () => void;
    disable: () => void;
    showProgress: (leaveActive?: boolean) => void;
    hideProgress: () => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
  };

  // HapticFeedback
  HapticFeedback: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
    selectionChanged: () => void;
  };

  // Popup
  showPopup: (params: {
    title?: string;
    message: string;
    buttons?: Array<{
      id?: string;
      type?: 'default' | 'ok' | 'close' | 'cancel' | 'destructive';
      text?: string;
    }>;
  }, callback?: (buttonId: string) => void) => void;

  showAlert: (message: string, callback?: () => void) => void;
  showConfirm: (message: string, callback?: (confirmed: boolean) => void) => void;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: WebApp;
    };
  }
}

export function useTelegram() {
  const [webApp, setWebApp] = useState<WebApp | null>(null);
  const [user, setUser] = useState<TelegramUser | null>(null);
  const [colorScheme, setColorScheme] = useState<'light' | 'dark'>('light');
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;

    if (tg) {
      setWebApp(tg);
      setUser(tg.initDataUnsafe.user || null);
      setColorScheme(tg.colorScheme);

      // Сообщаем Telegram, что приложение готово
      tg.ready();
      tg.expand();

      setIsReady(true);

      // Применяем тему
      applyTheme(tg.themeParams, tg.colorScheme);
    } else {
      // Для разработки без Telegram
      console.warn('Telegram WebApp not available. Running in dev mode.');
      setIsReady(true);
    }
  }, []);

  const applyTheme = useCallback((theme: ThemeParams, scheme: 'light' | 'dark') => {
    const root = document.documentElement;

    // Устанавливаем CSS переменные из темы Telegram
    root.style.setProperty('--tg-theme-bg-color', theme.bg_color || (scheme === 'dark' ? '#1c1c1e' : '#ffffff'));
    root.style.setProperty('--tg-theme-text-color', theme.text_color || (scheme === 'dark' ? '#ffffff' : '#000000'));
    root.style.setProperty('--tg-theme-hint-color', theme.hint_color || (scheme === 'dark' ? '#8e8e93' : '#999999'));
    root.style.setProperty('--tg-theme-link-color', theme.link_color || '#007aff');
    root.style.setProperty('--tg-theme-button-color', theme.button_color || '#007aff');
    root.style.setProperty('--tg-theme-button-text-color', theme.button_text_color || '#ffffff');
    root.style.setProperty('--tg-theme-secondary-bg-color', theme.secondary_bg_color || (scheme === 'dark' ? '#2c2c2e' : '#f2f2f7'));
    root.style.setProperty('--tg-theme-header-bg-color', theme.header_bg_color || theme.bg_color || (scheme === 'dark' ? '#1c1c1e' : '#ffffff'));
    root.style.setProperty('--tg-theme-accent-text-color', theme.accent_text_color || '#007aff');
    root.style.setProperty('--tg-theme-section-bg-color', theme.section_bg_color || (scheme === 'dark' ? '#2c2c2e' : '#ffffff'));
    root.style.setProperty('--tg-theme-section-header-text-color', theme.section_header_text_color || (scheme === 'dark' ? '#8e8e93' : '#6d6d72'));
    root.style.setProperty('--tg-theme-subtitle-text-color', theme.subtitle_text_color || (scheme === 'dark' ? '#8e8e93' : '#999999'));
    root.style.setProperty('--tg-theme-destructive-text-color', theme.destructive_text_color || '#ff3b30');

    // Устанавливаем атрибут для CSS
    root.setAttribute('data-theme', scheme);
  }, []);

  // Получить initData для отправки на сервер
  const getInitData = useCallback(() => {
    return webApp?.initData || '';
  }, [webApp]);

  // Показать BackButton
  const showBackButton = useCallback((onClick: () => void) => {
    if (webApp?.BackButton) {
      webApp.BackButton.show();
      webApp.BackButton.onClick(onClick);
    }
  }, [webApp]);

  // Скрыть BackButton
  const hideBackButton = useCallback(() => {
    if (webApp?.BackButton) {
      webApp.BackButton.hide();
    }
  }, [webApp]);

  // Показать MainButton
  const showMainButton = useCallback((text: string, onClick: () => void) => {
    if (webApp?.MainButton) {
      webApp.MainButton.setText(text);
      webApp.MainButton.show();
      webApp.MainButton.onClick(onClick);
    }
  }, [webApp]);

  // Скрыть MainButton
  const hideMainButton = useCallback(() => {
    if (webApp?.MainButton) {
      webApp.MainButton.hide();
    }
  }, [webApp]);

  // Haptic feedback
  const hapticFeedback = useCallback((type: 'light' | 'medium' | 'heavy' | 'success' | 'warning' | 'error') => {
    if (webApp?.HapticFeedback) {
      if (['light', 'medium', 'heavy', 'rigid', 'soft'].includes(type)) {
        webApp.HapticFeedback.impactOccurred(type as 'light' | 'medium' | 'heavy');
      } else {
        webApp.HapticFeedback.notificationOccurred(type as 'success' | 'warning' | 'error');
      }
    }
  }, [webApp]);

  // Показать alert
  const showAlert = useCallback((message: string) => {
    if (webApp) {
      webApp.showAlert(message);
    } else {
      alert(message);
    }
  }, [webApp]);

  // Показать confirm
  const showConfirm = useCallback((message: string): Promise<boolean> => {
    return new Promise((resolve) => {
      if (webApp) {
        webApp.showConfirm(message, resolve);
      } else {
        resolve(confirm(message));
      }
    });
  }, [webApp]);

  // Закрыть приложение
  const close = useCallback(() => {
    webApp?.close();
  }, [webApp]);

  return {
    webApp,
    user,
    colorScheme,
    isReady,
    getInitData,
    showBackButton,
    hideBackButton,
    showMainButton,
    hideMainButton,
    hapticFeedback,
    showAlert,
    showConfirm,
    close,
  };
}

export type { TelegramUser, ThemeParams, WebApp };
