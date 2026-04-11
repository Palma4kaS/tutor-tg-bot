import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../../hooks/useTelegram';
import { getDebtors } from '../../api/teacher';
import type { TeacherStudent } from '../../types';

export default function Debtors() {
  const navigate = useNavigate();
  const { showBackButton, hideBackButton } = useTelegram();
  const [debtors, setDebtors] = useState<TeacherStudent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    showBackButton(() => navigate('/'));
    getDebtors()
      .then(setDebtors)
      .catch(console.error)
      .finally(() => setLoading(false));
    return () => hideBackButton();
  }, [showBackButton, hideBackButton, navigate]);

  const totalDebt = debtors.reduce((sum, s) => sum + s.total_debt, 0);

  if (loading) {
    return <div className="loading"><div className="spinner" /></div>;
  }

  return (
    <div className="page">
      <div className="page-header" style={{ paddingBottom: 24 }}>
        <h1>Должники</h1>
        <p>{debtors.length} чел. · {totalDebt} ₽ итого</p>
      </div>

      <div style={{ padding: '0 16px' }}>
        {debtors.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🎉</div>
            <p>Должников нет!</p>
          </div>
        ) : (
          <div className="list">
            {debtors.map((student) => (
              <div
                key={student.user_id}
                className="list-item"
                onClick={() => navigate(`/teacher/students/${student.user_id}`)}
              >
                <div
                  className="list-item-icon"
                  style={{ background: 'linear-gradient(135deg, #eb3349 0%, #f45c43 100%)' }}
                >
                  💸
                </div>
                <div className="list-item-content">
                  <div className="list-item-title">{student.name}</div>
                  <div className="list-item-subtitle">
                    {student.unpaid_lessons_count} занятий · {student.grade} класс
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 16, color: '#eb3349' }}>
                    {student.total_debt} ₽
                  </div>
                  <div className="list-item-arrow" style={{ marginLeft: 0 }}>›</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
