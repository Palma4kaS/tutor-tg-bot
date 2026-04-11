import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTelegram } from '../../hooks/useTelegram';
import { getDashboard } from '../../api/teacher';
import type { DashboardStats, TeacherLesson } from '../../types';

function LessonRow({ lesson }: { lesson: TeacherLesson }) {
  const isPaid = lesson.payment_status === 'paid';
  return (
    <div className="lesson-card" style={{ cursor: 'default' }}>
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 12,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 20,
          flexShrink: 0,
        }}
      >
        📚
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="list-item-title" style={{ fontSize: 15 }}>{lesson.student_name}</div>
        <div className="list-item-subtitle">{lesson.time_range}</div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{lesson.price} ₽</div>
        <span className={`badge ${isPaid ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: 11 }}>
          {isPaid ? 'Оплачено' : 'Не оплачено'}
        </span>
      </div>
    </div>
  );
}

export default function TeacherHome() {
  const { user, hideBackButton } = useTelegram();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    hideBackButton();
    getDashboard()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [hideBackButton]);

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
      </div>
    );
  }

  const displayName = user?.first_name || 'Учитель';

  return (
    <div className="page">
      <div className="page-header" style={{ paddingBottom: 32 }}>
        <div style={{ fontSize: 48, marginBottom: 16, animation: 'float 3s ease-in-out infinite' }}>
          🎓
        </div>
        <h1>Привет, {displayName}!</h1>
        <p>Панель учителя</p>
      </div>

      {/* Счётчики */}
      <div style={{ padding: '0 16px', marginBottom: 24, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Link to="/teacher/students" style={{ textDecoration: 'none' }}>
          <div className="card" style={{ textAlign: 'center', padding: '20px 12px' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>👥</div>
            <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 700, fontSize: 28, color: 'var(--tg-theme-text-color)' }}>
              {stats?.new_students_count ?? 0}
            </div>
            <div style={{ color: 'var(--tg-theme-hint-color)', fontSize: 13, marginTop: 4 }}>
              Новых учеников
            </div>
          </div>
        </Link>

        <Link to="/teacher/debtors" style={{ textDecoration: 'none' }}>
          <div className="card" style={{ textAlign: 'center', padding: '20px 12px' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>💰</div>
            <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 700, fontSize: 28, color: stats?.debtors_count ? '#eb3349' : 'var(--tg-theme-text-color)' }}>
              {stats?.debtors_count ?? 0}
            </div>
            <div style={{ color: 'var(--tg-theme-hint-color)', fontSize: 13, marginTop: 4 }}>
              Должников
            </div>
          </div>
        </Link>
      </div>

      {/* Меню */}
      <div className="menu-grid" style={{ marginBottom: 24 }}>
        <Link to="/teacher/schedule" className="menu-item">
          <span className="menu-item-icon">📅</span>
          <span className="menu-item-label">Расписание</span>
        </Link>
        <Link to="/teacher/students" className="menu-item">
          <span className="menu-item-icon">👨‍🎓</span>
          <span className="menu-item-label">Ученики</span>
        </Link>
        <Link to="/teacher/debtors" className="menu-item">
          <span className="menu-item-icon">💸</span>
          <span className="menu-item-label">Должники</span>
        </Link>
        <Link to="/teacher/settings" className="menu-item">
          <span className="menu-item-icon">⚙️</span>
          <span className="menu-item-label">Настройки</span>
        </Link>
      </div>

      {/* Занятия сегодня */}
      <div className="section" style={{ padding: '0 16px' }}>
        <div className="section-title">
          Сегодня — {stats?.today_lessons_count ?? 0} занятий
        </div>
        {stats?.today_lessons.length ? (
          <div className="list">
            {stats.today_lessons.map((lesson) => (
              <LessonRow key={lesson.id} lesson={lesson} />
            ))}
          </div>
        ) : (
          <div className="empty-state" style={{ padding: '32px 0' }}>
            <div className="empty-state-icon">🌙</div>
            <p>Занятий сегодня нет</p>
          </div>
        )}
      </div>
    </div>
  );
}
