import apiClient from './client';
import type {
  StudentProfile,
  Lesson,
  LessonsHistory,
  HomeworkList,
  HomeworkDetail,
  LessonDetail,
  UpdateProfileResponse,
} from '../types';

// === Профиль ===

export async function getProfile(): Promise<StudentProfile> {
  const response = await apiClient.get<StudentProfile>('/student/profile');
  return response.data;
}

export async function updateName(name: string): Promise<UpdateProfileResponse> {
  const response = await apiClient.put<UpdateProfileResponse>('/student/profile/name', { name });
  return response.data;
}

export async function updateGrade(grade: number): Promise<UpdateProfileResponse> {
  const response = await apiClient.put<UpdateProfileResponse>('/student/profile/grade', { grade });
  return response.data;
}

export async function updateSubject(subject: string): Promise<UpdateProfileResponse> {
  const response = await apiClient.put<UpdateProfileResponse>('/student/profile/subject', { subject });
  return response.data;
}

// === Занятия ===

export async function getUpcomingLessons(): Promise<Lesson[]> {
  const response = await apiClient.get<Lesson[]>('/student/lessons/upcoming');
  return response.data;
}

export async function getLessonsHistory(): Promise<LessonsHistory> {
  const response = await apiClient.get<LessonsHistory>('/student/lessons/history');
  return response.data;
}

// === Домашние задания ===

export async function getHomeworkList(): Promise<HomeworkList> {
  const response = await apiClient.get<HomeworkList>('/student/homework');
  return response.data;
}

export async function getHomeworkDetail(lessonId: number): Promise<HomeworkDetail> {
  const response = await apiClient.get<HomeworkDetail>(`/student/homework/${lessonId}`);
  return response.data;
}

export async function getLessonDetail(lessonId: number): Promise<LessonDetail> {
  const response = await apiClient.get<LessonDetail>(`/student/lessons/${lessonId}`);
  return response.data;
}

export async function fetchTelegramFile(fileId: string): Promise<Blob> {
  const response = await apiClient.get(`/student/file/${fileId}/proxy`, {
    responseType: 'blob',
  });
  return response.data;
}
