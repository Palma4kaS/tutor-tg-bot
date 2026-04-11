import { useEffect, useState } from 'react';
import { fetchTelegramFile } from '../api/student';

interface TelegramImageProps {
  fileId: string;
  alt?: string;
}

export function TelegramImage({ fileId, alt = 'Image' }: TelegramImageProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;

    const loadImage = async () => {
      try {
        const blob = await fetchTelegramFile(fileId);
        objectUrl = URL.createObjectURL(blob);
        setImageUrl(objectUrl);
      } catch (err) {
        console.error('Failed to load image:', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    loadImage();

    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [fileId]);

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100px',
        color: 'var(--tg-theme-hint-color)'
      }}>
        <div className="spinner" style={{ width: '24px', height: '24px' }} />
      </div>
    );
  }

  if (error || !imageUrl) {
    return (
      <div style={{
        textAlign: 'center',
        padding: '16px',
        color: 'var(--tg-theme-hint-color)'
      }}>
        Не удалось загрузить изображение
      </div>
    );
  }

  return (
    <img
      src={imageUrl}
      alt={alt}
      style={{
        maxWidth: '100%',
        borderRadius: '8px',
        display: 'block'
      }}
    />
  );
}

interface TelegramFileDownloadProps {
  fileId: string;
  fileName?: string;
}

export function TelegramFileDownload({ fileId, fileName = 'file' }: TelegramFileDownloadProps) {
  const [loading, setLoading] = useState(false);

  const handleDownload = async () => {
    setLoading(true);
    try {
      const blob = await fetchTelegramFile(fileId);
      const url = URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download file:', err);
      alert('Не удалось скачать файл');
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleDownload}
      disabled={loading}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '12px 16px',
        background: 'var(--tg-theme-button-color)',
        color: 'var(--tg-theme-button-text-color)',
        border: 'none',
        borderRadius: '8px',
        cursor: loading ? 'wait' : 'pointer',
        width: '100%',
        justifyContent: 'center',
        fontSize: '14px',
        fontWeight: 500,
        opacity: loading ? 0.7 : 1
      }}
    >
      {loading ? (
        <>
          <div className="spinner" style={{ width: '16px', height: '16px' }} />
          Загрузка...
        </>
      ) : (
        <>
          <span>📥</span>
          Скачать: {fileName}
        </>
      )}
    </button>
  );
}
