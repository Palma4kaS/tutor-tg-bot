import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../../hooks/useTelegram';
import { getPriceSettings, updatePriceSettings } from '../../api/teacher';
import type { PriceSettings } from '../../types';

interface FieldConfig {
  key: keyof Omit<PriceSettings, 'updated_at'>;
  label: string;
  description: string;
  icon: string;
}

const FIELDS: FieldConfig[] = [
  { key: 'base_price', label: 'Базовая цена (офлайн)', description: 'Стандартная цена за занятие', icon: '🏠' },
  { key: 'online_surcharge', label: 'Доплата за онлайн', description: 'Добавляется к базовой цене', icon: '💻' },
  { key: 'grade_9_surcharge', label: 'Доплата за 9 класс', description: 'Добавляется к базовой цене', icon: '9️⃣' },
  { key: 'grade_10_11_surcharge', label: 'Доплата за 10-11 класс', description: 'Добавляется к базовой цене', icon: '🎓' },
  { key: 'profile_surcharge', label: 'Доплата за профиль', description: 'Для профильного уровня', icon: '⭐' },
];

export default function Settings() {
  const navigate = useNavigate();
  const { showBackButton, hideBackButton, showAlert } = useTelegram();
  const [settings, setSettings] = useState<Omit<PriceSettings, 'updated_at'>>({
    base_price: 0,
    online_surcharge: 0,
    grade_9_surcharge: 0,
    grade_10_11_surcharge: 0,
    profile_surcharge: 0,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  useEffect(() => {
    showBackButton(() => navigate('/'));
    getPriceSettings()
      .then((data) => {
        setSettings({
          base_price: data.base_price,
          online_surcharge: data.online_surcharge,
          grade_9_surcharge: data.grade_9_surcharge,
          grade_10_11_surcharge: data.grade_10_11_surcharge,
          profile_surcharge: data.profile_surcharge,
        });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
    return () => hideBackButton();
  }, [showBackButton, hideBackButton, navigate]);

  const startEdit = (key: string, value: number) => {
    setEditingKey(key);
    setEditValue(String(value));
  };

  const saveField = async () => {
    if (!editingKey) return;
    const num = parseFloat(editValue);
    if (isNaN(num) || num < 0) {
      showAlert('Введите корректное число');
      return;
    }
    const updated = { ...settings, [editingKey]: num };
    setSettings(updated);
    setEditingKey(null);

    setSaving(true);
    try {
      await updatePriceSettings(updated);
    } catch {
      showAlert('Ошибка при сохранении');
    } finally {
      setSaving(false);
    }
  };

  const cancelEdit = () => {
    setEditingKey(null);
    setEditValue('');
  };

  if (loading) {
    return <div className="loading"><div className="spinner" /></div>;
  }

  // Пример итоговой цены
  const exampleOnlineProfile = settings.base_price + settings.online_surcharge + settings.profile_surcharge;
  const exampleOffline9 = settings.base_price + settings.grade_9_surcharge;

  return (
    <div className="page">
      <div className="page-header" style={{ paddingBottom: 24 }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>⚙️</div>
        <h1>Настройки цен</h1>
        {saving && <p style={{ color: 'var(--tg-theme-hint-color)' }}>Сохранение...</p>}
      </div>

      <div style={{ padding: '0 16px' }}>
        <div className="list" style={{ marginBottom: 24 }}>
          {FIELDS.map((field) => (
            <div key={field.key}>
              {editingKey === field.key ? (
                <div style={{ padding: '16px' }}>
                  <div style={{ marginBottom: 8, fontWeight: 600, fontFamily: "'Outfit', sans-serif" }}>
                    {field.icon} {field.label}
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      className="input"
                      type="number"
                      inputMode="numeric"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      autoFocus
                      style={{ flex: 1 }}
                    />
                    <button className="btn btn-primary" onClick={saveField} style={{ padding: '12px 16px' }}>
                      ✓
                    </button>
                    <button className="btn btn-secondary" onClick={cancelEdit} style={{ padding: '12px 16px' }}>
                      ✕
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  className="list-item"
                  onClick={() => startEdit(field.key, settings[field.key])}
                >
                  <div
                    className="list-item-icon"
                    style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', fontSize: 20 }}
                  >
                    {field.icon}
                  </div>
                  <div className="list-item-content">
                    <div className="list-item-title">{field.label}</div>
                    <div className="list-item-subtitle">{field.description}</div>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 18, color: 'var(--tg-theme-accent-text-color)', marginLeft: 12 }}>
                    {settings[field.key]} ₽
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Примеры итоговых цен */}
        <div className="section-title">Примеры итоговых цен</div>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ color: 'var(--tg-theme-hint-color)' }}>Онлайн + профиль</span>
            <span style={{ fontWeight: 700 }}>{exampleOnlineProfile} ₽</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--tg-theme-hint-color)' }}>Офлайн + 9 класс</span>
            <span style={{ fontWeight: 700 }}>{exampleOffline9} ₽</span>
          </div>
        </div>
      </div>
    </div>
  );
}
