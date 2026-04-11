import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useTelegram } from '../../hooks/useTelegram';
import { getLessonDetail, updateLessonPayment, updateLessonStatus, updateLessonHomework } from '../../api/teacher';
import type { TeacherLessonDetail } from '../../types';

const STATUS_LABELS: Record<string, string> = {
  scheduled: 'Запланировано',
  completed: 'Проведено',
  cancelled: 'Отменено',
};

const PAYMENT_LABELS: Record<string, string> = {
  paid: 'Оплачено',
  unpaid: 'Не оплачено',
  pending: 'Ожидает',
};

export default function TeacherLessonDetailPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const [searchParams] = useSearchParams();
  const studentId = searchParams.get('studentId');
  const navigate = useNavigate();
  const { showBackButton, hideBackButton, showAlert, showConfirm } = useTelegram();

  const [lesson, setLesson] = useState<TeacherLessonDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingHw, setEditingHw] = useState(false);
  const [hwValue, setHwValue] = useState('');

  useEffect(() => {
    showBackButton(() => {
      if (studentId) navigate(`/teacher/students/${studentId}`);
      else navigate('/');
    });
    getLessonDetail(Number(lessonId))
      .then((data) => {
        setLesson(data);
        setHwValue(data.homework || '');
      })
      .catch(console.error)
      .finally(() => setLoading(false));
    return () => hideBackButton();
  }, [lessonId, studentId, showBackButton, hideBackButton, navigate]);

  const handlePayment = async () => {
    if (!lesson) return;
    const newStatus = lesson.payment_status === 'paid' ? 'unpaid' : 'paid';
    setSaving(true);
    try {
      const updated = await updateLessonPayment(Number(lessonId), newStatus);
      setLesson(updated);
    } catch {
      showAlert('Ошибка при сохранении');
    } finally {
      setSaving(false);
    }
  };

  const handleStatus = async (newStatus: string) => {
    if (!lesson) return;
    const confirmed = await showConfirm(
      `Изменить статус на "${STATUS_LABELS[newStatus]}"?`
    );
    if (!confirmed) return;
    setSaving(true);
    try {
      const updated = await updateLessonStatus(Number(lessonId), newStatus);
      setLesson(updated);
    } catch {
      showAlert('Ошибка при сохранении');
    } finally {
      setSaving(false);
    }
  };

  const saveHomework = async () => {
    setSaving(true);
    try {
      const updated = await updateLessonHomework(Number(lessonId), hwValue);
      setLesson(updated);
      setEditingHw(false);
    } catch {
      showAlert('Ошибка при сохранении');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="loading"><div className="spinner" /></div>;
  }

  if (!lesson) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">❌</div>
        <p>Занятие не найдено</p>
      </div>
    );
  }

  const isPaid = lesson.payment_status === 'paid';
  const isCompleted = lesson.status === 'completed';
  const isCancelled = lesson.status === 'cancelled';
  const formatLabel = lesson.lesson_format === 'online' ? 'Онлайн' : lesson.lesson_format === 'offline' ? 'Офлайн' : '—';

  return (
    <div className="page">
      <div className="page-header" style={{ paddingBottom: 24 }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>
          {isCompleted ? '✅' : isCancelled ? '❌' : '📅'}
        </div>
        <h1>{lesson.formatted_date}</h1>
        <p>{lesson.student_name}</p>
        {saving && <p style={{ color: 'var(--tg-theme-hint-color)', fontSize: 13 }}>Сохранение...</p>}
      </div>

      <div style={{ padding: '0 16px' }}>

        {/* Основная информация */}
        <div className="section-title">Занятие</div>
        <div className="list" style={{ marginBottom: 24 }}>
          <div className="list-item" style={{ cursor: 'default' }}>
            <div className="list-item-icon" style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>🕐</div>
            <div className="list-item-content">
              <div className="list-item-title">{lesson.time_range}</div>
              <div className="list-item-subtitle">{lesson.duration} мин</div>
            </div>
          </div>
          <div className="list-item" style={{ cursor: 'default' }}>
            <div className="list-item-icon" style={{ background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' }}>💻</div>
            <div className="list-item-content">
              <div className="list-item-title">{formatLabel}</div>
              <div className="list-item-subtitle">Формат</div>
            </div>
          </div>
          <div className="list-item" style={{ cursor: 'default' }}>
            <div className="list-item-icon" style={{ background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)' }}>💰</div>
            <div className="list-item-content">
              <div className="list-item-title">{lesson.price} ₽</div>
              <div className="list-item-subtitle">Стоимость</div>
            </div>
          </div>
        </div>

        {/* Статус занятия */}
        <div className="section-title">Статус занятия</div>
        <div className="list" style={{ marginBottom: 24 }}>
          {(['scheduled', 'completed', 'cancelled'] as const).map((s) => (
            <div
              key={s}
              className="list-item"
              onClick={() => lesson.status !== s && handleStatus(s)}
              style={{ opacity: saving ? 0.6 : 1 }}
            >
              <div style={{ fontSize: 20, width: 32, textAlign: 'center' }}>
                {s === 'scheduled' ? '📅' : s === 'completed' ? '✅' : '❌'}
              </div>
              <div className="list-item-content">
                <div className="list-item-title">{STATUS_LABELS[s]}</div>
              </div>
              {lesson.status === s && (
                <div style={{ color: 'var(--tg-theme-accent-text-color)', fontWeight: 700, fontSize: 18 }}>✓</div>
              )}
            </div>
          ))}
        </div>

        {/* Оплата */}
        {!isCancelled && (
          <>
            <div className="section-title">Оплата</div>
            <div className="card" style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{PAYMENT_LABELS[lesson.payment_status]}</div>
                  <div style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)' }}>
                    {isPaid ? 'Занятие оплачено' : 'Ожидает оплаты'}
                  </div>
                </div>
                <button
                  className={`btn ${isPaid ? 'btn-secondary' : 'btn-primary'}`}
                  style={{ padding: '10px 16px', fontSize: 14 }}
                  onClick={handlePayment}
                  disabled={saving}
                >
                  {isPaid ? 'Отменить' : 'Оплачено ✓'}
                </button>
              </div>
            </div>
          </>
        )}

        {/* Домашнее задание */}
        {!isCancelled && (
          <>
            <div className="section-title">Домашнее задание</div>
            <div className="card" style={{ marginBottom: 32 }}>
              {editingHw ? (
                <div>
                  <textarea
                    className="input"
                    rows={4}
                    value={hwValue}
                    onChange={(e) => setHwValue(e.target.value)}
                    placeholder="Введите задание..."
                    style={{ width: '100%', resize: 'none', marginBottom: 10, boxSizing: 'border-box' }}
                    autoFocus
                  />
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-primary" style={{ flex: 1 }} onClick={saveHomework} disabled={saving}>
                      Сохранить
                    </button>
                    <button className="btn btn-secondary" onClick={() => { setEditingHw(false); setHwValue(lesson.homework || ''); }}>
                      Отмена
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ marginBottom: 10, minHeight: 40, color: lesson.homework ? 'inherit' : 'var(--tg-theme-hint-color)' }}>
                    {lesson.homework || 'Не задано'}
                  </div>
                  <button
                    className="btn btn-secondary"
                    style={{ width: '100%', fontSize: 14 }}
                    onClick={() => setEditingHw(true)}
                  >
                    {lesson.homework ? 'Изменить' : '+ Задать ДЗ'}
                  </button>
                </div>
              )}
            </div>
          </>
        )}

      </div>
    </div>
  );
}
