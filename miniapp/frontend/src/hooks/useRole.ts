import { useEffect, useState } from 'react';
import { getMyRole } from '../api/teacher';

type Role = 'teacher' | 'student' | null;

export function useRole() {
  const [role, setRole] = useState<Role>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMyRole()
      .then((data) => setRole(data.role))
      .catch(() => setRole('student')) // при ошибке показываем студенческий интерфейс
      .finally(() => setLoading(false));
  }, []);

  return { role, loading };
}
