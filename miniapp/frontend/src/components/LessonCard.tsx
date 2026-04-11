import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../hooks/useTelegram';
import type { Lesson } from '../types';

interface LessonCardProps {
  lesson: Lesson;
  showPaymentStatus?: boolean;
}

export default function LessonCard({ lesson, showPaymentStatus = false }: LessonCardProps) {
  const navigate = useNavigate();
  const { hapticFeedback } = useTelegram();

  const handleClick = () => {
    hapticFeedback('light');
    navigate(`/lessons/${lesson.id}`);
  };

  const getStatusConfig = () => {
    if (lesson.payment_status === 'unpaid' && lesson.status === 'completed') {
      return {
        icon: '❌',
        bgColor: 'linear-gradient(135deg, rgba(235, 51, 73, 0.15) 0%, rgba(244, 92, 67, 0.15) 100%)',
        iconBg: 'linear-gradient(135deg, #eb3349 0%, #f45c43 100%)',
      };
    }
    if (lesson.status === 'completed' && lesson.payment_status === 'paid') {
      return {
        icon: '✅',
        bgColor: 'linear-gradient(135deg, rgba(17, 153, 142, 0.15) 0%, rgba(56, 239, 125, 0.15) 100%)',
        iconBg: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
      };
    }
    return {
      icon: '⏳',
      bgColor: 'linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%)',
      iconBg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    };
  };

  const getHomeworkBadge = () => {
    if (!lesson.has_homework) return null;

    if (lesson.homework_status === 'completed') {
      return (
        <span
          style={{
            padding: '3px 8px',
            borderRadius: '6px',
            fontSize: '11px',
            fontWeight: '600',
            background: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
            color: 'white',
            fontFamily: "'Outfit', sans-serif",
            letterSpacing: '0.3px',
          }}
        >
          ✅ ДЗ
        </span>
      );
    }

    return (
      <span
        style={{
          padding: '3px 8px',
          borderRadius: '6px',
          fontSize: '11px',
          fontWeight: '600',
          background: 'linear-gradient(135deg, #f2994a 0%, #f2c94c 100%)',
          color: 'white',
          fontFamily: "'Outfit', sans-serif",
          letterSpacing: '0.3px',
        }}
      >
        📖 ДЗ
      </span>
    );
  };

  const statusConfig = getStatusConfig();
  const homeworkBadge = getHomeworkBadge();

  return (
    <div
      className="lesson-card"
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
          {lesson.formatted_date}
        </div>
        <div
          style={{
            fontSize: '14px',
            color: 'var(--tg-theme-hint-color)',
          }}
        >
          {lesson.time_range}
        </div>
      </div>

      <div
        style={{
          textAlign: 'right',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          gap: '6px',
        }}
      >
        <div
          style={{
            fontWeight: '700',
            fontSize: '18px',
            fontFamily: "'Outfit', sans-serif",
            color: 'var(--tg-theme-text-color)',
          }}
        >
          {lesson.price.toFixed(0)}₽
        </div>

        {homeworkBadge && homeworkBadge}

        {showPaymentStatus && lesson.payment_status === 'unpaid' && (
          <span
            style={{
              padding: '4px 10px',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: '600',
              background: 'linear-gradient(135deg, #eb3349 0%, #f45c43 100%)',
              color: 'white',
              fontFamily: "'Outfit', sans-serif",
              letterSpacing: '0.3px',
              boxShadow: '0 2px 8px rgba(235, 51, 73, 0.3)',
            }}
          >
            Не оплачено
          </span>
        )}
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
