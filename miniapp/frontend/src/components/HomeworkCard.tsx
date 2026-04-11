import { useTelegram } from '../hooks/useTelegram';
import type { HomeworkItem } from '../types';

interface HomeworkCardProps {
  homework: HomeworkItem;
  onClick: () => void;
}

export default function HomeworkCard({ homework, onClick }: HomeworkCardProps) {
  const { hapticFeedback } = useTelegram();

  const handleClick = () => {
    hapticFeedback('light');
    onClick();
  };

  const getStatusConfig = () => {
    if (homework.homework_status === 'completed') {
      return {
        icon: '✅',
        bgColor: 'linear-gradient(135deg, rgba(17, 153, 142, 0.15) 0%, rgba(56, 239, 125, 0.15) 100%)',
        iconBg: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
        badge: 'Выполнено',
        badgeBg: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
      };
    }
    if (homework.has_homework) {
      return {
        icon: '📝',
        bgColor: 'linear-gradient(135deg, rgba(240, 147, 251, 0.15) 0%, rgba(245, 87, 108, 0.15) 100%)',
        iconBg: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
        badge: 'Есть ДЗ',
        badgeBg: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
      };
    }
    return {
      icon: '📅',
      bgColor: 'linear-gradient(135deg, rgba(142, 142, 147, 0.15) 0%, rgba(174, 174, 178, 0.15) 100%)',
      iconBg: 'linear-gradient(135deg, #8e8e93 0%, #aeaeb2 100%)',
      badge: 'ДЗ нет',
      badgeBg: 'linear-gradient(135deg, #8e8e93 0%, #aeaeb2 100%)',
    };
  };

  const statusConfig = getStatusConfig();

  return (
    <div
      className="homework-card"
      onClick={handleClick}
      style={{
        background: statusConfig.bgColor,
      }}
    >
      <div
        style={{
          width: '52px',
          height: '52px',
          borderRadius: '14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: statusConfig.iconBg,
          fontSize: '24px',
          flexShrink: 0,
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
        }}
      >
        {statusConfig.icon}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontWeight: '600',
            fontSize: '16px',
            fontFamily: "'Outfit', sans-serif",
            marginBottom: '4px',
            color: 'var(--tg-theme-text-color)',
          }}
        >
          {homework.formatted_date}
        </div>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '3px 8px',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: '600',
            background: statusConfig.badgeBg,
            color: 'white',
            fontFamily: "'Outfit', sans-serif",
            letterSpacing: '0.3px',
          }}
        >
          {statusConfig.badge}
        </div>
      </div>

      <div
        style={{
          color: 'var(--tg-theme-hint-color)',
          fontSize: '20px',
          marginLeft: '8px',
          transition: 'transform 0.2s ease',
        }}
      >
        ›
      </div>
    </div>
  );
}
