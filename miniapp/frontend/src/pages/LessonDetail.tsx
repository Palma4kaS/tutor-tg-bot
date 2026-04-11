import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTelegram } from '../hooks/useTelegram';
import { getLessonDetail } from '../api/student';
import { TelegramImage, TelegramFileDownload } from '../components/TelegramFile';
import type { LessonDetail as LessonDetailType } from '../types';

export default function LessonDetail() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const navigate = useNavigate();
  const { showBackButton, hideBackButton } = useTelegram();

  const [lesson, setLesson] = useState<LessonDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleBack = useCallback(() => {
    navigate('/lessons');
  }, [navigate]);

  useEffect(() => {
    showBackButton(handleBack);
    return () => hideBackButton();
  }, [showBackButton, hideBackButton, handleBack]);

  useEffect(() => {
    if (lessonId) {
      loadLesson(parseInt(lessonId));
    }
  }, [lessonId]);

  const loadLesson = async (id: number) => {
    try {
      const data = await getLessonDetail(id);
      setLesson(data);
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

  if (!lesson) {
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

  const getStatusBadge = () => {
    if (lesson.status === 'completed') {
      return <span className="badge badge-success">✅ Проведено</span>;
    }
    if (lesson.status === 'cancelled') {
      return <span className="badge badge-error">❌ Отменено</span>;
    }
    return <span className="badge badge-warning">⏳ Запланировано</span>;
  };

  const getPaymentBadge = () => {
    if (lesson.payment_status === 'paid') {
      return <span className="badge badge-success">✅ Оплачено</span>;
    }
    if (lesson.payment_status === 'pending') {
      return <span className="badge badge-warning">⏳ Ожидает</span>;
    }
    return <span className="badge badge-error">❌ Не оплачено</span>;
  };

  const hasHomework = lesson.homework && lesson.homework.trim();

  return (
    <div className="page">
      <div className="page-header">
        <h1>📚 Занятие</h1>
      </div>

      <div className="container">
        <div
          className="card"
          style={{
            background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)',
            borderLeft: '4px solid #667eea',
          }}
        >
          <div className="card-header">
            <span className="card-title">📅 {lesson.formatted_date}</span>
          </div>
          <div className="card-subtitle">
            🕐 {lesson.time_range}
          </div>

          <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--tg-theme-hint-color)', fontWeight: '500' }}>Стоимость:</span>
              <span
                style={{
                  fontWeight: '700',
                  fontSize: '18px',
                  fontFamily: "'Outfit', sans-serif",
                  color: 'var(--tg-theme-text-color)',
                }}
              >
                {lesson.price.toFixed(0)}₽
              </span>
            </div>

            {lesson.lesson_format && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--tg-theme-hint-color)', fontWeight: '500' }}>Формат:</span>
                <span style={{ fontWeight: '600' }}>
                  {lesson.lesson_format === 'online' ? '💻 Онлайн' : '🏠 Очно'}
                </span>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--tg-theme-hint-color)', fontWeight: '500' }}>Статус:</span>
              {getStatusBadge()}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--tg-theme-hint-color)', fontWeight: '500' }}>Оплата:</span>
              {getPaymentBadge()}
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-title">📝 Домашнее задание</div>
          <div className="card">
            {hasHomework ? (
              <>
                <p style={{ whiteSpace: 'pre-wrap', marginBottom: lesson.homework_status ? '16px' : 0, lineHeight: '1.6' }}>
                  {lesson.homework}
                </p>
                {lesson.homework_status && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingTop: '12px', borderTop: '1px solid rgba(0, 0, 0, 0.05)' }}>
                    <span style={{ color: 'var(--tg-theme-hint-color)', fontWeight: '500' }}>Статус:</span>
                    {lesson.homework_status === 'completed' ? (
                      <span className="badge badge-success">✅ Выполнено</span>
                    ) : lesson.homework_status === 'assigned' ? (
                      <span className="badge badge-warning">📝 Задано</span>
                    ) : (
                      <span className="badge badge-error">❌ Не выполнено</span>
                    )}
                  </div>
                )}
              </>
            ) : (
              <p style={{ color: 'var(--tg-theme-hint-color)', textAlign: 'center', padding: '20px 0' }}>
                Домашнее задание не задано
              </p>
            )}
          </div>
        </div>

        {lesson.homework_photo_file_id && (
          <div className="section">
            <div className="section-title">📷 Фото к заданию</div>
            <div className="card" style={{ padding: '8px' }}>
              <TelegramImage fileId={lesson.homework_photo_file_id} alt="Фото к ДЗ" />
            </div>
          </div>
        )}

        {lesson.homework_file_id && (
          <div className="section">
            <div className="section-title">📎 Файл к заданию</div>
            <div className="card">
              <TelegramFileDownload
                fileId={lesson.homework_file_id}
                fileName={lesson.homework_file_name || 'homework_file'}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
