import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTelegram } from '../hooks/useTelegram';
import { getHomeworkDetail } from '../api/student';
import { TelegramImage, TelegramFileDownload } from '../components/TelegramFile';
import type { HomeworkDetail as HomeworkDetailType } from '../types';

export default function HomeworkDetail() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const navigate = useNavigate();
  const { showBackButton, hideBackButton } = useTelegram();

  const [homework, setHomework] = useState<HomeworkDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleBack = useCallback(() => {
    navigate('/homework');
  }, [navigate]);

  useEffect(() => {
    showBackButton(handleBack);
    return () => hideBackButton();
  }, [showBackButton, hideBackButton, handleBack]);

  useEffect(() => {
    if (lessonId) {
      loadHomework(parseInt(lessonId));
    }
  }, [lessonId]);

  const loadHomework = async (id: number) => {
    try {
      const data = await getHomeworkDetail(id);
      setHomework(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <div className="container">
          <div className="alert alert-error">{error}</div>
        </div>
      </div>
    );
  }

  if (!homework) {
    return (
      <div className="page">
        <div className="container">
          <div className="empty-state">
            <div className="empty-state-icon">📭</div>
            <p>Занятие не найдено</p>
          </div>
        </div>
      </div>
    );
  }

  const hasHomework = homework.homework && homework.homework.trim();

  return (
    <div className="page">
      <div className="page-header">
        <h1>📖 Домашнее задание</h1>
      </div>

      <div className="container">
        <div
          className="card"
          style={{
            background: 'linear-gradient(135deg, rgba(240, 147, 251, 0.1) 0%, rgba(245, 87, 108, 0.1) 100%)',
            borderLeft: '4px solid #f093fb',
          }}
        >
          <div className="card-header">
            <span className="card-title">📅 {homework.formatted_date}</span>
          </div>
          <div className="card-subtitle">
            🕐 {homework.time_range}
          </div>
        </div>

        <div className="section">
          <div className="section-title">📝 Задание</div>
          <div className="card">
            {hasHomework ? (
              <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{homework.homework}</p>
            ) : (
              <p style={{ color: 'var(--tg-theme-hint-color)', textAlign: 'center', padding: '20px 0' }}>
                Домашнее задание не задано
              </p>
            )}
          </div>
        </div>

        {homework.homework_photo_file_id && (
          <div className="section">
            <div className="section-title">📷 Фото</div>
            <div className="card" style={{ padding: '8px' }}>
              <TelegramImage fileId={homework.homework_photo_file_id} alt="Фото к ДЗ" />
            </div>
          </div>
        )}

        {homework.homework_file_id && (
          <div className="section">
            <div className="section-title">📎 Файл</div>
            <div className="card">
              <TelegramFileDownload
                fileId={homework.homework_file_id}
                fileName={homework.homework_file_name || 'homework_file'}
              />
            </div>
          </div>
        )}

        {homework.homework_status && (
          <div className="section">
            <div
              className="card"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '12px',
                padding: '20px',
              }}
            >
              <span style={{ fontWeight: '500' }}>Статус:</span>
              {homework.homework_status === 'completed' ? (
                <span className="badge badge-success">✅ Выполнено</span>
              ) : homework.homework_status === 'assigned' ? (
                <span className="badge badge-warning">📝 Задано</span>
              ) : (
                <span className="badge badge-error">❌ Не выполнено</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
