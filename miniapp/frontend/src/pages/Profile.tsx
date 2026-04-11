import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../hooks/useTelegram';
import { getProfile, updateName, updateGrade, updateSubject } from '../api/student';
import EditModal from '../components/EditModal';
import type { StudentProfile } from '../types';

type EditField = 'name' | 'grade' | 'subject' | null;

export default function Profile() {
  const navigate = useNavigate();
  const { showBackButton, hideBackButton, hapticFeedback, showAlert } = useTelegram();

  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [editField, setEditField] = useState<EditField>(null);
  const [saving, setSaving] = useState(false);

  const handleBack = useCallback(() => {
    navigate('/');
  }, [navigate]);

  useEffect(() => {
    showBackButton(handleBack);
    return () => hideBackButton();
  }, [showBackButton, hideBackButton, handleBack]);

  useEffect(() => {
    loadProfile();
  }, []);

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

  const handleEdit = (field: EditField) => {
    hapticFeedback('light');
    setEditField(field);
  };

  const handleSave = async (value: string | number) => {
    if (!profile) return;

    setSaving(true);
    try {
      let response;

      switch (editField) {
        case 'name':
          response = await updateName(value as string);
          break;
        case 'grade':
          response = await updateGrade(value as number);
          break;
        case 'subject':
          response = await updateSubject(value as string);
          break;
      }

      if (response) {
        if (response.success) {
          hapticFeedback('success');
          await loadProfile();
        } else {
          hapticFeedback('error');
          showAlert(response.message);
        }
      }
    } catch (error) {
      hapticFeedback('error');
      showAlert(error instanceof Error ? error.message : 'Ошибка сохранения');
    } finally {
      setSaving(false);
      setEditField(null);
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '—';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('ru-RU');
    } catch {
      return dateStr;
    }
  };

  const getSubjectLabel = (subject?: string) => {
    if (!subject) return '—';
    return subject === 'профиль' ? 'Профиль' : 'База';
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="page">
        <div className="container">
          <div className="alert alert-error">Профиль не найден</div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>👤 Мой профиль</h1>
      </div>

      <div className="container">
        <div className="section">
          <div className="list">
            <div
              className="list-item"
              onClick={() => profile.can_change_name && handleEdit('name')}
              style={{ cursor: profile.can_change_name ? 'pointer' : 'default' }}
            >
              <div
                className="list-item-icon"
                style={{
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
                }}
              >
                ✏️
              </div>
              <div className="list-item-content">
                <div className="list-item-title">Имя</div>
                <div className="list-item-subtitle">{profile.name}</div>
              </div>
              {profile.can_change_name ? (
                <span className="list-item-arrow">›</span>
              ) : (
                <span className="badge badge-warning">⏳</span>
              )}
            </div>

            <div
              className="list-item"
              onClick={() => profile.can_change_grade && handleEdit('grade')}
              style={{ cursor: profile.can_change_grade ? 'pointer' : 'default' }}
            >
              <div
                className="list-item-icon"
                style={{
                  background: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
                  boxShadow: '0 4px 12px rgba(17, 153, 142, 0.3)',
                }}
              >
                🎓
              </div>
              <div className="list-item-content">
                <div className="list-item-title">Класс</div>
                <div className="list-item-subtitle">{profile.grade} класс</div>
              </div>
              {profile.can_change_grade ? (
                <span className="list-item-arrow">›</span>
              ) : (
                <span className="badge badge-warning">⏳</span>
              )}
            </div>

            {profile.grade >= 10 && (
              <div
                className="list-item"
                onClick={() => profile.can_change_subject && handleEdit('subject')}
                style={{ cursor: profile.can_change_subject ? 'pointer' : 'default' }}
              >
                <div
                  className="list-item-icon"
                  style={{
                    background: 'linear-gradient(135deg, #f2994a 0%, #f2c94c 100%)',
                    boxShadow: '0 4px 12px rgba(242, 153, 74, 0.3)',
                  }}
                >
                  📊
                </div>
                <div className="list-item-content">
                  <div className="list-item-title">Направление</div>
                  <div className="list-item-subtitle">{getSubjectLabel(profile.subject)}</div>
                </div>
                {profile.can_change_subject ? (
                  <span className="list-item-arrow">›</span>
                ) : (
                  <span className="badge badge-warning">⏳</span>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="section">
          <div className="section-title">Информация</div>
          <div className="list">
            <div className="list-item" style={{ cursor: 'default' }}>
              <div
                className="list-item-icon"
                style={{
                  background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                  boxShadow: '0 4px 12px rgba(240, 147, 251, 0.3)',
                }}
              >
                📞
              </div>
              <div className="list-item-content">
                <div className="list-item-title">Телефон</div>
                <div className="list-item-subtitle">{profile.phone}</div>
              </div>
            </div>

            <div className="list-item" style={{ cursor: 'default' }}>
              <div
                className="list-item-icon"
                style={{
                  background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                  boxShadow: '0 4px 12px rgba(79, 172, 254, 0.3)',
                }}
              >
                📅
              </div>
              <div className="list-item-content">
                <div className="list-item-title">Дата регистрации</div>
                <div className="list-item-subtitle">{formatDate(profile.registration_date)}</div>
              </div>
            </div>
          </div>
        </div>

        <div
          style={{
            padding: '16px 20px',
            background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)',
            borderRadius: '14px',
            textAlign: 'center',
            borderLeft: '4px solid #667eea',
          }}
        >
          <p style={{ color: 'var(--tg-theme-hint-color)', fontSize: '14px', lineHeight: '1.6' }}>
            ℹ️ Каждый параметр можно менять один раз в неделю
          </p>
        </div>
      </div>

      {editField && (
        <EditModal
          field={editField}
          currentValue={
            editField === 'name'
              ? profile.name
              : editField === 'grade'
              ? profile.grade
              : profile.subject || ''
          }
          onSave={handleSave}
          onClose={() => setEditField(null)}
          saving={saving}
        />
      )}
    </div>
  );
}
