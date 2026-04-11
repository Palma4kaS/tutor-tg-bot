import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../hooks/useTelegram';
import { getHomeworkList } from '../api/student';
import HomeworkCard from '../components/HomeworkCard';
import type { HomeworkList as HomeworkListType } from '../types';

export default function Homework() {
  const navigate = useNavigate();
  const { showBackButton, hideBackButton } = useTelegram();

  const [homework, setHomework] = useState<HomeworkListType | null>(null);
  const [loading, setLoading] = useState(true);

  const handleBack = useCallback(() => {
    navigate('/');
  }, [navigate]);

  useEffect(() => {
    showBackButton(handleBack);
    return () => hideBackButton();
  }, [showBackButton, hideBackButton, handleBack]);

  useEffect(() => {
    loadHomework();
  }, []);

  const loadHomework = async () => {
    try {
      const data = await getHomeworkList();
      setHomework(data);
    } catch (error) {
      console.error('Failed to load homework:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleHomeworkClick = (lessonId: number) => {
    navigate(`/homework/${lessonId}`);
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
      </div>
    );
  }

  const isEmpty =
    !homework ||
    (homework.active.length === 0 && homework.recent.length === 0);

  return (
    <div className="page">
      <div className="page-header">
        <h1>📖 Домашние задания</h1>
      </div>

      <div className="container">
        {isEmpty ? (
          <div className="empty-state">
            <div className="empty-state-icon">📭</div>
            <p>Нет домашних заданий</p>
          </div>
        ) : (
          <>
            {homework && homework.active.length > 0 && (
              <div className="section">
                <div className="section-title">📅 Прошлая неделя</div>
                <div className="list">
                  {homework.active.map((item) => (
                    <HomeworkCard
                      key={item.id}
                      homework={item}
                      onClick={() => handleHomeworkClick(item.id)}
                    />
                  ))}
                </div>
              </div>
            )}

            {homework && homework.recent.length > 0 && (
              <div className="section">
                <div className="section-title">🔮 Следующая неделя</div>
                <div className="list">
                  {homework.recent.map((item) => (
                    <HomeworkCard
                      key={item.id}
                      homework={item}
                      onClick={() => handleHomeworkClick(item.id)}
                    />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
