import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTelegram } from '../hooks/useTelegram';
import { getProfile } from '../api/student';
import type { StudentProfile } from '../types';

export default function Home() {
  const { user, hideBackButton } = useTelegram();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    hideBackButton();
    loadProfile();
  }, [hideBackButton]);

  const loadProfile = async () => {
    try {
      const data = await getProfile();
      setProfile(data);
    } catch (error) {
      console.error('Failed to load profile:', error);
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

  const displayName = profile?.name || user?.first_name || 'Ученик';

  return (
    <div className="page">
      <div className="page-header" style={{ paddingBottom: '32px' }}>
        <div
          style={{
            fontSize: '48px',
            marginBottom: '16px',
            animation: 'float 3s ease-in-out infinite',
          }}
        >
          👋
        </div>
        <h1>Привет, {displayName}!</h1>
        <p>Добро пожаловать в личный кабинет</p>
      </div>

      <div className="menu-grid">
        <Link to="/lessons" className="menu-item">
          <span className="menu-item-icon">📚</span>
          <span className="menu-item-label">Занятия</span>
        </Link>

        <Link to="/homework" className="menu-item">
          <span className="menu-item-icon">📖</span>
          <span className="menu-item-label">ДЗ</span>
        </Link>

        <Link to="/materials" className="menu-item">
          <span className="menu-item-icon">📄</span>
          <span className="menu-item-label">Материалы</span>
        </Link>

        <Link to="/profile" className="menu-item">
          <span className="menu-item-icon">👤</span>
          <span className="menu-item-label">Профиль</span>
        </Link>
      </div>

      {profile && profile.grade && (
        <div
          style={{
            margin: '24px 16px 0',
            padding: '20px',
            background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)',
            borderRadius: '16px',
            textAlign: 'center',
            animation: 'fadeInUp 0.5s ease-out 0.5s both',
          }}
        >
          <div style={{ fontSize: '32px', marginBottom: '8px' }}>🎓</div>
          <div
            style={{
              fontSize: '16px',
              fontWeight: '600',
              fontFamily: "'Outfit', sans-serif",
              color: 'var(--tg-theme-text-color)',
            }}
          >
            {profile.grade} класс
            {profile.subject && profile.grade >= 10 && (
              <span style={{ color: 'var(--tg-theme-hint-color)', fontWeight: '500' }}>
                {' • '}
                {profile.subject === 'профиль' ? 'Профиль' : 'База'}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
