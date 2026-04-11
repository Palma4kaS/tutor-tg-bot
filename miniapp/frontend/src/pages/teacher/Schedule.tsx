import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../../hooks/useTelegram';
import { getWeekSchedule } from '../../api/teacher';
import type { WeekSchedule, TeacherLesson } from '../../types';

const WEEKDAYS: Record<string, string> = {
  '0': 'Воскресенье', '1': 'Понедельник', '2': 'Вторник',
  '3': 'Среда', '4': 'Четверг', '5': 'Пятница', '6': 'Суббота',
};

function formatDateHeader(dateStr: string): string {
  const date = new Date(dateStr);
  const day = date.getDate().toString().padStart(2, '0');
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  const weekday = WEEKDAYS[date.getDay().toString()];
  return `${day}.${month} — ${weekday}`;
}

function LessonCard({ lesson }: { lesson: TeacherLesson }) {
  const isPaid = lesson.payment_status === 'paid';
  const isCompleted = lesson.status === 'completed';

  return (
    <div
      className="lesson-card"
      style={{ cursor: 'default', opacity: isCompleted ? 0.7 : 1 }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 12,
          background: isCompleted
            ? 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'
            : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 20,
          flexShrink: 0,
        }}
      >
        {isCompleted ? '✅' : '📚'}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="list-item-title" style={{ fontSize: 15 }}>{lesson.student_name}</div>
        <div className="list-item-subtitle">
          {lesson.time_range}
          {lesson.lesson_format && ` · ${lesson.lesson_format === 'online' ? 'Онлайн' : 'Офлайн'}`}
        </div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{lesson.price} ₽</div>
        <span className={`badge ${isPaid ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: 11 }}>
          {isPaid ? 'Оплачено' : 'Не оплачено'}
        </span>
      </div>
    </div>
  );
}

export default function Schedule() {
  const navigate = useNavigate();
  const { showBackButton, hideBackButton } = useTelegram();
  const [schedule, setSchedule] = useState<WeekSchedule | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    showBackButton(() => navigate('/'));
    getWeekSchedule()
      .then(setSchedule)
      .catch(console.error)
      .finally(() => setLoading(false));
    return () => hideBackButton();
  }, [showBackButton, hideBackButton, navigate]);

  if (loading) {
    return <div className="loading"><div className="spinner" /></div>;
  }

  const days = schedule?.days ?? {};
  const sortedDates = Object.keys(days).sort();

  return (
    <div className="page">
      <div className="page-header" style={{ paddingBottom: 24 }}>
        <h1>Расписание</h1>
        <p>Ближайшие 7 дней</p>
      </div>

      <div style={{ padding: '0 16px' }}>
        {sortedDates.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📅</div>
            <p>Занятий на ближайшую неделю нет</p>
          </div>
        ) : (
          sortedDates.map((date) => (
            <div key={date} className="section">
              <div className="section-title">{formatDateHeader(date)}</div>
              <div className="list">
                {days[date].map((lesson) => (
                  <LessonCard key={lesson.id} lesson={lesson} />
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
