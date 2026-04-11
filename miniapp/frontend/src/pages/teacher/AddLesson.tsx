import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTelegram } from '../../hooks/useTelegram';

export default function AddLesson() {
  const { studentId } = useParams<{ studentId: string }>();
  const navigate = useNavigate();
  const { showBackButton, hideBackButton } = useTelegram();

  useEffect(() => {
    showBackButton(() => navigate(`/teacher/students/${studentId}`));
    return () => hideBackButton();
  }, [studentId, showBackButton, hideBackButton, navigate]);

  return (
    <div className="page">
      <div className="page-header" style={{ paddingBottom: 24 }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>➕</div>
        <h1>Новое занятие</h1>
        <p>В разработке</p>
      </div>
    </div>
  );
}
