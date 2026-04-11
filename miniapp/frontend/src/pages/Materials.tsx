import { useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../hooks/useTelegram';

export default function Materials() {
  const navigate = useNavigate();
  const { showBackButton, hideBackButton, hapticFeedback } = useTelegram();

  const handleBack = useCallback(() => {
    navigate('/');
  }, [navigate]);

  useEffect(() => {
    showBackButton(handleBack);
    return () => hideBackButton();
  }, [showBackButton, hideBackButton, handleBack]);

  const handleLinkClick = (url: string) => {
    hapticFeedback('light');
    window.open(url, '_blank');
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>📄 Дополнительные материалы</h1>
        <p>Полезные ресурсы для подготовки</p>
      </div>

      <div className="container">
        <div className="section">
          <div className="section-title">Подготовка к экзаменам</div>
          <div className="list">
            <div
              className="list-item"
              onClick={() => handleLinkClick('https://telegra.ph/Test-1-09-03-4')}
            >
              <div
                className="list-item-icon"
                style={{
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
                }}
              >
                📚
              </div>
              <div className="list-item-content">
                <div className="list-item-title">Материалы для ОГЭ</div>
                <div className="list-item-subtitle">9 класс</div>
              </div>
              <span
                style={{
                  color: 'var(--tg-theme-hint-color)',
                  fontSize: '20px',
                  marginLeft: '8px',
                }}
              >
                ↗
              </span>
            </div>

            <div
              className="list-item"
              onClick={() => handleLinkClick('https://telegra.ph/Dop-materialy-dlya-podgotovki-dlya-EGEH-09-03')}
            >
              <div
                className="list-item-icon"
                style={{
                  background: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
                  boxShadow: '0 4px 12px rgba(17, 153, 142, 0.3)',
                }}
              >
                📖
              </div>
              <div className="list-item-content">
                <div className="list-item-title">Материалы для ЕГЭ</div>
                <div className="list-item-subtitle">10-11 класс</div>
              </div>
              <span
                style={{
                  color: 'var(--tg-theme-hint-color)',
                  fontSize: '20px',
                  marginLeft: '8px',
                }}
              >
                ↗
              </span>
            </div>
          </div>
        </div>

        <div
          style={{
            padding: '16px 20px',
            background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)',
            borderRadius: '14px',
            textAlign: 'center',
            borderLeft: '4px solid #667eea',
          }}
        >
          <p style={{ color: 'var(--tg-theme-hint-color)', fontSize: '14px', lineHeight: '1.6' }}>
            💡 Материалы открываются в браузере
          </p>
        </div>
      </div>
    </div>
  );
}
