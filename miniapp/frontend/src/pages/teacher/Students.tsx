import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../../hooks/useTelegram';
import { getStudents } from '../../api/teacher';
import type { TeacherStudent } from '../../types';

export default function Students() {
  const navigate = useNavigate();
  const { showBackButton, hideBackButton } = useTelegram();
  const [students, setStudents] = useState<TeacherStudent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    showBackButton(() => navigate('/'));
    getStudents()
      .then(setStudents)
      .catch(console.error)
      .finally(() => setLoading(false));
    return () => hideBackButton();
  }, [showBackButton, hideBackButton, navigate]);

  const filtered = students.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return <div className="loading"><div className="spinner" /></div>;
  }

  return (
    <div className="page">
      <div className="page-header" style={{ paddingBottom: 24 }}>
        <h1>Ученики</h1>
        <p>{students.length} чел.</p>
      </div>

      <div style={{ padding: '0 16px 16px' }}>
        <input
          className="input"
          placeholder="Поиск по имени..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div style={{ padding: '0 16px' }}>
        {filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👨‍🎓</div>
            <p>Ученики не найдены</p>
          </div>
        ) : (
          <div className="list">
            {filtered.map((student) => (
              <div
                key={student.user_id}
                className="list-item"
                onClick={() => navigate(`/teacher/students/${student.user_id}`)}
              >
                <div
                  className="list-item-icon"
                  style={{
                    background: student.is_new
                      ? 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'
                      : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  }}
                >
                  {student.is_new ? '🆕' : '👤'}
                </div>
                <div className="list-item-content">
                  <div className="list-item-title">{student.name}</div>
                  <div className="list-item-subtitle">
                    {student.grade} класс
                    {student.subject && ` · ${student.subject}`}
                    {student.total_debt > 0 && (
                      <span style={{ color: '#eb3349', marginLeft: 6 }}>
                        · Долг: {student.total_debt} ₽
                      </span>
                    )}
                  </div>
                </div>
                <div className="list-item-arrow">›</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
