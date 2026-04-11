import apiClient from './client';
import type {
  RoleResponse,
  DashboardStats,
  WeekSchedule,
  TeacherStudent,
  TeacherStudentDetail,
  TeacherStudentLessons,
  TeacherLesson,
  TeacherLessonDetail,
  PriceSettings,
} from '../types';

export async function getMyRole(): Promise<RoleResponse> {
  const response = await apiClient.get<RoleResponse>('/me/role');
  return response.data;
}

export async function getDashboard(): Promise<DashboardStats> {
  const response = await apiClient.get<DashboardStats>('/teacher/dashboard');
  return response.data;
}

export async function getWeekSchedule(): Promise<WeekSchedule> {
  const response = await apiClient.get<WeekSchedule>('/teacher/schedule/week');
  return response.data;
}

export async function getStudents(): Promise<TeacherStudent[]> {
  const response = await apiClient.get<TeacherStudent[]>('/teacher/students');
  return response.data;
}

export async function getStudentDetail(studentId: number): Promise<TeacherStudentDetail> {
  const response = await apiClient.get<TeacherStudentDetail>(`/teacher/students/${studentId}`);
  return response.data;
}

export async function getStudentLessons(studentId: number): Promise<TeacherStudentLessons> {
  const response = await apiClient.get<TeacherStudentLessons>(`/teacher/students/${studentId}/lessons`);
  return response.data;
}

export async function getStudentLessonsHistory(studentId: number, offset: number = 0, limit: number = 20): Promise<TeacherLesson[]> {
  const response = await apiClient.get<TeacherLesson[]>(`/teacher/students/${studentId}/lessons/history`, {
    params: { offset, limit },
  });
  return response.data;
}

export async function getDebtors(): Promise<TeacherStudent[]> {
  const response = await apiClient.get<TeacherStudent[]>('/teacher/debtors');
  return response.data;
}

export async function getLessonDetail(lessonId: number): Promise<TeacherLessonDetail> {
  const response = await apiClient.get<TeacherLessonDetail>(`/teacher/lessons/${lessonId}`);
  return response.data;
}

export async function updateLessonPayment(lessonId: number, paymentStatus: string): Promise<TeacherLessonDetail> {
  const response = await apiClient.patch<TeacherLessonDetail>(`/teacher/lessons/${lessonId}/payment`, {
    payment_status: paymentStatus,
  });
  return response.data;
}

export async function updateLessonStatus(lessonId: number, status: string): Promise<TeacherLessonDetail> {
  const response = await apiClient.patch<TeacherLessonDetail>(`/teacher/lessons/${lessonId}/status`, {
    status,
  });
  return response.data;
}

export async function updateLessonHomework(lessonId: number, homework: string): Promise<TeacherLessonDetail> {
  const response = await apiClient.patch<TeacherLessonDetail>(`/teacher/lessons/${lessonId}/homework`, {
    homework,
  });
  return response.data;
}

export async function getPriceSettings(): Promise<PriceSettings> {
  const response = await apiClient.get<PriceSettings>('/teacher/settings');
  return response.data;
}

export async function updatePriceSettings(data: Omit<PriceSettings, 'updated_at'>): Promise<PriceSettings> {
  const response = await apiClient.put<PriceSettings>('/teacher/settings', data);
  return response.data;
}
