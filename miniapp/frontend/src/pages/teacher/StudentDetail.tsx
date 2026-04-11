import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTelegram } from '../../hooks/useTelegram';
import { getStudentDetail, getStudentLessons, getStudentLessonsHistory } from '../../api/teacher';
import type { TeacherStudentDetail, TeacherStudentLessons, TeacherLesson } from '../../types';

const STATUS_ICON: Record<string, string> = {
  scheduled: '🔜',
  completed_paid: '✅',
  completed_unpaid: '🔴',
  cancelled: '❌',
};

function getLessonIcon(lesson: TeacherLesson): string {
  if (lesson.status === 'cancelled') return STATUS_ICON.cancelled;
  if (lesson.status === 'scheduled') return STATUS_ICON.scheduled;
  if (lesson.payment_status === 'paid') return STATUS_ICON.completed_paid;
  return STATUS_ICON.completed_unpaid;
}

function formatLabel(lesson: TeacherLesson): string {
  const format = lesson.lesson_format === 'online' ? 'Онлайн' : lesson.lesson_format === 'offline' ? 'Офлайн' : '';
  return [lesson.time_range, format].filter(Boolean).join(' · ');
}

function LessonRow({ lesson, onClick }: { lesson: TeacherLesson; onClick: () => void }) {
  const isPaid = lesson.payment_status === 'paid';
  const isCancelled = lesson.status === 'cancelled';
  const isScheduled = lesson.status === 'scheduled';

  return (
    <div
      className="list-item"
      onClick={onClick}
      style={{ opacity: isCancelled ? 0.55 : 1 }}
    >
      <div style={{ fontSize: 22, width: 32, textAlign: 'center', flexShrink: 0 }}>
        {getLessonIcon(lesson)}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="list-item-title" style={{ fontSize: 14 }}>
          {lesson.formatted_date}
        </div>
        <div className="list-item-subtitle">{formatLabel(lesson)}</div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>{lesson.price} ₽</div>
        {!isCancelled && !isScheduled && (
          <span
            className={`badge ${isPaid ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: 10, marginTop: 2 }}
          >
            {isPaid ? 'Оплачено' : 'Долг'}
          </span>
        )}
      </div>
    </div>
  );
}

export default function StudentDetail() {
  const { studentId } = useParams<{ studentId: string }>();
  const navigate = useNavigate();
  const { showBackButton, hideBackButton } = useTelegram();

  const [student, setStudent] = useState<TeacherStudentDetail | null>(null);
  const [timeline, setTimeline] = useState<TeacherStudentLessons>({ upcoming: [], recent: [], has_more: false });
  const [history, setHistory] = useState<TeacherLesson[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    showBackButton(() => navigate('/teacher/students'));
    const id = Number(studentId);
    Promise.all([getStudentDetail(id), getStudentLessons(id)])
      .then(([s, l]) => {
        setStudent(s);
        setTimeline(l);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
    return () => hideBackButton();
  }, [studentId, showBackButton, hideBackButton, navigate]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const older = await getStudentLessonsHistory(Number(studentId), history.length);
      setHistory((prev) => [...prev, ...older]);
      if (older.length < 20) {
        setTimeline((prev) => ({ ...prev, has_more: false }));
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingMore(false);
    }
  };

  const openLesson = (lessonId: number) => {
    navigate(`/teacher/lessons/${lessonId}?studentId=${studentId}`);
  };

  if (loading) {
    return <div className="loading"><div className="spinner" /></div>;
  }

  if (!student) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">❌</div>
        <p>Ученик не найден</p>
      </div>
    );
  }

  const totalShown = timeline.upcoming.length + timeline.recent.length + history.length;

  return (
    <div className="page">
      <div className="page-header" style={{ paddingBottom: 24 }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>👤</div>
        <h1>{student.name}</h1>
        <p>
          {student.grade} класс
          {student.subject && ` · ${student.subject}`}
        </p>
      </div>

      {/* Долг */}
      {student.total_debt > 0 && (
        <div style={{ padding: '0 16px', marginBottom: 16 }}>
          <div className="debt-alert">
            <span className="debt-alert-icon">⚠️</span>
            <span className="debt-alert-text">
              Долг: {student.unpaid_lessons_count} зан.
            </span>
            <span className="debt-alert-amount">{student.total_debt} ₽</span>
          </div>
        </div>
      )}

      {/* Информация */}
      <div style={{ padding: '0 16px', marginBottom: 24 }}>
        <div className="section-title">Информация</div>
        <div className="list">
          <div className="list-item" style={{ cursor: 'default' }}>
            <div className="list-item-icon" style={{ background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' }}>📱</div>
            <div className="list-item-content">
              <div className="list-item-title">{student.phone}</div>
              <div className="list-item-subtitle">Телефон</div>
            </div>
          </div>
          <div className="list-item" style={{ cursor: 'default' }}>
            <div className="list-item-icon" style={{ background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)' }}>📊</div>
            <div className="list-item-content">
              <div className="list-item-title">{student.total_lessons_count} занятий</div>
              <div className="list-item-subtitle">Всего проведено</div>
            </div>
          </div>
          {student.registration_format && (
            <div className="list-item" style={{ cursor: 'default' }}>
              <div className="list-item-icon" style={{ background: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)' }}>🏠</div>
              <div className="list-item-content">
                <div className="list-item-title">
                  {student.registration_format === 'online' ? 'Онлайн' : 'Офлайн'}
                </div>
                <div className="list-item-subtitle">Формат обучения</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Занятия — таймлайн */}
      <div style={{ padding: '0 16px', paddingBottom: 32 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div className="section-title" style={{ marginBottom: 0 }}>
            Занятия {totalShown > 0 && `(${totalShown})`}
          </div>
          <button
            className="btn btn-primary"
            style={{ padding: '8px 14px', fontSize: 13 }}
            onClick={() => navigate(`/teacher/students/${studentId}/add-lesson`)}
          >
            + Добавить
          </button>
        </div>

        {totalShown === 0 ? (
          <div className="empty-state" style={{ padding: '32px 0' }}>
            <div className="empty-state-icon">📚</div>
            <p>Занятий ещё нет</p>
          </div>
        ) : (
          <div className="list">
            {/* Предстоящие */}
            {timeline.upcoming.map((lesson) => (
              <LessonRow key={lesson.id} lesson={lesson} onClick={() => openLesson(lesson.id)} />
            ))}

            {/* Разделитель "сегодня" */}
            {(timeline.upcoming.length > 0 || timeline.recent.length > 0 || history.length > 0) && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 16px',
                color: 'var(--tg-theme-hint-color)',
                fontSize: 12,
              }}>
                <div style={{ flex: 1, height: 1, background: 'var(--tg-theme-hint-color)', opacity: 0.3 }} />
                <span>сегодня</span>
                <div style={{ flex: 1, height: 1, background: 'var(--tg-theme-hint-color)', opacity: 0.3 }} />
              </div>
            )}

            {/* Прошедшие (последние 14 дней) */}
            {timeline.recent.map((lesson) => (
              <LessonRow key={lesson.id} lesson={lesson} onClick={() => openLesson(lesson.id)} />
            ))}

            {/* Старые (загруженные через "показать ещё") */}
            {history.map((lesson) => (
              <LessonRow key={lesson.id} lesson={lesson} onClick={() => openLesson(lesson.id)} />
            ))}
          </div>
        )}

        {/* Кнопка показать ещё */}
        {timeline.has_more && (
          <button
            className="btn btn-secondary"
            style={{ width: '100%', marginTop: 12 }}
            onClick={loadMore}
            disabled={loadingMore}
          >
            {loadingMore ? 'Загрузка...' : 'Показать ещё'}
          </button>
        )}
      </div>
    </div>
  );
}
