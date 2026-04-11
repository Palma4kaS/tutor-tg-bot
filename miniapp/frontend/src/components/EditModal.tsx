import { useState } from 'react';

interface EditModalProps {
  field: 'name' | 'grade' | 'subject';
  currentValue: string | number;
  onSave: (value: string | number) => void;
  onClose: () => void;
  saving: boolean;
}

export default function EditModal({
  field,
  currentValue,
  onSave,
  onClose,
  saving,
}: EditModalProps) {
  const [value, setValue] = useState<string | number>(currentValue);

  const getTitle = () => {
    switch (field) {
      case 'name':
        return 'Изменить имя';
      case 'grade':
        return 'Изменить класс';
      case 'subject':
        return 'Изменить направление';
    }
  };

  const handleSave = () => {
    if (field === 'name' && typeof value === 'string' && value.trim().length < 2) {
      return;
    }
    onSave(value);
  };

  const renderInput = () => {
    switch (field) {
      case 'name':
        return (
          <div className="input-group">
            <label className="input-label">Введите имя</label>
            <input
              type="text"
              className="input"
              value={value as string}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Введите имя"
              minLength={2}
              maxLength={100}
              autoFocus
            />
          </div>
        );

      case 'grade':
        return (
          <div className="input-group">
            <label className="input-label">Выберите класс</label>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: '10px',
              }}
            >
              {[5, 6, 7, 8, 9, 10, 11].map((grade) => (
                <button
                  key={grade}
                  className={`btn ${value === grade ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setValue(grade)}
                  style={{
                    padding: '14px',
                    fontSize: '18px',
                    fontWeight: '700',
                  }}
                >
                  {grade}
                </button>
              ))}
            </div>
          </div>
        );

      case 'subject':
        return (
          <div className="input-group">
            <label className="input-label">Выберите направление</label>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                className={`btn btn-block ${
                  value === 'база' ? 'btn-primary' : 'btn-secondary'
                }`}
                onClick={() => setValue('база')}
                style={{ padding: '18px', fontSize: '16px' }}
              >
                <div style={{ fontSize: '24px', marginBottom: '4px' }}>📐</div>
                <div>База</div>
              </button>
              <button
                className={`btn btn-block ${
                  value === 'профиль' ? 'btn-primary' : 'btn-secondary'
                }`}
                onClick={() => setValue('профиль')}
                style={{ padding: '18px', fontSize: '16px' }}
              >
                <div style={{ fontSize: '24px', marginBottom: '4px' }}>📈</div>
                <div>Профиль</div>
              </button>
            </div>
          </div>
        );
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{getTitle()}</h2>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        {renderInput()}

        <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
          <button
            className="btn btn-secondary btn-block"
            onClick={onClose}
            disabled={saving}
            style={{ padding: '14px 20px' }}
          >
            Отмена
          </button>
          <button
            className="btn btn-primary btn-block"
            onClick={handleSave}
            disabled={
              saving ||
              (field === 'name' && typeof value === 'string' && value.trim().length < 2)
            }
            style={{ padding: '14px 20px' }}
          >
            {saving ? (
              <>
                <div
                  style={{
                    display: 'inline-block',
                    width: '14px',
                    height: '14px',
                    border: '2px solid white',
                    borderTopColor: 'transparent',
                    borderRadius: '50%',
                    animation: 'spin 0.6s linear infinite',
                    marginRight: '8px',
                    verticalAlign: 'middle',
                  }}
                />
                Сохранение...
              </>
            ) : (
              'Сохранить'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
