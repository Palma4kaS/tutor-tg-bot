import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../hooks/useTelegram';
import { getUpcomingLessons, getLessonsHistory } from '../api/student';
import LessonCard from '../components/LessonCard';
import type { Lesson, LessonsHistory } from '../types';

type TabType = 'upcoming' | 'history';

export default function Lessons() {
  const navigate = useNavigate();
  const { showBackButton, hideBackButton, hapticFeedback } = useTelegram();

  const [activeTab, setActiveTab] = useState<TabType>('upcoming');
  const [upcomingLessons, setUpcomingLessons] = useState<Lesson[]>([]);
  const [history, setHistory] = useState<LessonsHistory | null>(null);
  const [loading, setLoading] = useState(true);

  const handleBack = useCallback(() => {
    navigate('/');
  }, [navigate]);

  useEffect(() => {
    showBackButton(handleBack);
    return () => hideBackButton();
  }, [showBackButton, hideBackButton, handleBack]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [upcoming, hist] = await Promise.all([
        getUpcomingLessons(),
        getLessonsHistory(),
      ]);
      setUpcomingLessons(upcoming);
      setHistory(hist);
    } catch (error) {
      console.error('Failed to load lessons:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (tab: TabType) => {
    hapticFeedback('light');
    setActiveTab(tab);
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>📚 Мои занятия</h1>
      </div>

      <div className="container">
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'upcoming' ? 'active' : ''}`}
            onClick={() => handleTabChange('upcoming')}
          >
            🔮 Предстоящие
          </button>
          <button
            className={`tab ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => handleTabChange('history')}
          >
            📅 История
          </button>
        </div>

        {activeTab === 'upcoming' && (
          <div className="section">
            {upcomingLessons.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📭</div>
                <p>Нет предстоящих занятий</p>
              </div>
            ) : (
              <div className="list">
                {upcomingLessons.map((lesson) => (
                  <LessonCard key={lesson.id} lesson={lesson} />
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && history && (
          <>
            {history.unpaid.length > 0 && (
              <div className="section">
                <div className="debt-alert">
                  <span className="debt-alert-icon">⚠️</span>
                  <span className="debt-alert-text">
                    Неоплачено: {history.unpaid.length} зан.
                  </span>
                  <span className="debt-alert-amount">
                    {history.total_debt.toFixed(0)}₽
                  </span>
                </div>

                <div className="list">
                  {history.unpaid.map((lesson) => (
                    <LessonCard key={lesson.id} lesson={lesson} showPaymentStatus />
                  ))}
                </div>
              </div>
            )}

            {history.upcoming.length > 0 && (
              <div className="section">
                <div className="section-title">🔮 Предстоящие</div>
                <div className="list">
                  {history.upcoming.map((lesson) => (
                    <LessonCard key={lesson.id} lesson={lesson} />
                  ))}
                </div>
              </div>
            )}

            {history.past.length > 0 && (
              <div className="section">
                <div className="section-title">✅ Прошедшие</div>
                <div className="list">
                  {history.past.map((lesson) => (
                    <LessonCard key={lesson.id} lesson={lesson} />
                  ))}
                </div>
              </div>
            )}

            {history.unpaid.length === 0 &&
              history.upcoming.length === 0 &&
              history.past.length === 0 && (
                <div className="empty-state">
                  <div className="empty-state-icon">📭</div>
                  <p>История занятий пуста</p>
                </div>
              )}
          </>
        )}
      </div>
    </div>
  );
}
