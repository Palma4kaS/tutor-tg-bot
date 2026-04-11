// Профиль ученика
export interface StudentProfile {
  user_id: number;
  name: string;
  username?: string;
  phone: string;
  grade: number;
  subject?: string;
  registration_date?: string;

  // Флаги возможности изменения
  can_change_name: boolean;
  can_change_grade: boolean;
  can_change_subject: boolean;

  // Даты последних изменений
  last_name_change?: string;
  last_grade_change?: string;
  last_subject_change?: string;
}

// Занятие
export interface Lesson {
  id: number;
  lesson_date: string;
  lesson_time: string;
  duration: number;
  price: number;
  status: 'scheduled' | 'completed' | 'cancelled';
  payment_status: 'paid' | 'unpaid' | 'pending';
  lesson_format?: 'online' | 'offline';

  homework?: string;
  homework_status?: 'assigned' | 'completed' | 'not_done';

  has_homework: boolean;
  time_range?: string;
  formatted_date?: string;
}

// История занятий
export interface LessonsHistory {
  unpaid: Lesson[];
  upcoming: Lesson[];
  past: Lesson[];
  total_debt: number;
}

// Элемент списка ДЗ
export interface HomeworkItem {
  id: number;
  lesson_date: string;
  lesson_time: string;
  duration: number;
  has_homework: boolean;
  homework_status?: string;
  formatted_date?: string;
}

// Список ДЗ
export interface HomeworkList {
  active: HomeworkItem[];
  recent: HomeworkItem[];
}

// Детали ДЗ
export interface HomeworkDetail {
  id: number;
  lesson_date: string;
  lesson_time: string;
  duration: number;
  homework?: string;
  homework_status?: string;
  homework_photo_file_id?: string;
  homework_file_id?: string;
  homework_file_name?: string;
  formatted_date?: string;
  time_range?: string;
}

// Детальная информация о занятии
export interface LessonDetail {
  id: number;
  lesson_date: string;
  lesson_time: string;
  duration: number;
  price: number;
  status: 'scheduled' | 'completed' | 'cancelled';
  payment_status: 'paid' | 'unpaid' | 'pending';
  lesson_format?: 'online' | 'offline';

  homework?: string;
  homework_status?: 'assigned' | 'completed' | 'not_done';
  homework_photo_file_id?: string;
  homework_file_id?: string;
  homework_file_name?: string;

  formatted_date?: string;
  time_range?: string;
}

// Ответ на обновление профиля
export interface UpdateProfileResponse {
  success: boolean;
  message: string;
  can_change_again?: string;
}

// === Типы для учителя ===

export interface RoleResponse {
  role: 'teacher' | 'student';
}

export interface TeacherStudent {
  user_id: number;
  name: string;
  grade: number;
  subject?: string;
  phone: string;
  registration_date?: string;
  total_debt: number;
  unpaid_lessons_count: number;
  is_new: boolean;
}

export interface TeacherLesson {
  id: number;
  student_id: number;
  student_name: string;
  lesson_date: string;
  lesson_time: string;
  duration: number;
  price: number;
  status: string;
  payment_status: string;
  lesson_format?: string;
  has_homework: boolean;
  time_range?: string;
  formatted_date?: string;
}

export interface DashboardStats {
  new_students_count: number;
  debtors_count: number;
  today_lessons_count: number;
  today_lessons: TeacherLesson[];
}

export interface TeacherStudentDetail {
  user_id: number;
  name: string;
  grade: number;
  subject?: string;
  phone: string;
  registration_date?: string;
  registration_format?: string;
  total_debt: number;
  unpaid_lessons_count: number;
  total_lessons_count: number;
  is_new: boolean;
}

export interface WeekSchedule {
  days: Record<string, TeacherLesson[]>;
}

export interface TeacherStudentLessons {
  upcoming: TeacherLesson[];
  recent: TeacherLesson[];
  has_more: boolean;
}

export interface TeacherLessonDetail {
  id: number;
  student_id: number;
  student_name: string;
  lesson_date: string;
  lesson_time: string;
  duration: number;
  price: number;
  status: string;
  payment_status: string;
  lesson_format?: string;
  homework?: string;
  homework_status?: string;
  time_range?: string;
  formatted_date?: string;
}

export interface PriceSettings {
  base_price: number;
  online_surcharge: number;
  grade_9_surcharge: number;
  grade_10_11_surcharge: number;
  profile_surcharge: number;
  updated_at?: string;
}
