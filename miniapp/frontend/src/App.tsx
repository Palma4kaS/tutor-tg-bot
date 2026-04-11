import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useTelegram } from './hooks/useTelegram';
import { useRole } from './hooks/useRole';

// Страницы ученика
import Home from './pages/Home';
import Lessons from './pages/Lessons';
import LessonDetail from './pages/LessonDetail';
import Homework from './pages/Homework';
import HomeworkDetail from './pages/HomeworkDetail';
import Profile from './pages/Profile';
import Materials from './pages/Materials';

// Страницы учителя
import TeacherHome from './pages/teacher/TeacherHome';
import Schedule from './pages/teacher/Schedule';
import Students from './pages/teacher/Students';
import StudentDetail from './pages/teacher/StudentDetail';
import Debtors from './pages/teacher/Debtors';
import Settings from './pages/teacher/Settings';
import TeacherLessonDetail from './pages/teacher/TeacherLessonDetail';
import AddLesson from './pages/teacher/AddLesson';

import './styles/global.css';

function App() {
  const { isReady } = useTelegram();
  const { role, loading: roleLoading } = useRole();

  if (!isReady || roleLoading) {
    return (
      <div className="loading">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        {role === 'teacher' ? (
          <>
            <Route path="/" element={<TeacherHome />} />
            <Route path="/teacher/schedule" element={<Schedule />} />
            <Route path="/teacher/students" element={<Students />} />
            <Route path="/teacher/students/:studentId" element={<StudentDetail />} />
            <Route path="/teacher/debtors" element={<Debtors />} />
            <Route path="/teacher/settings" element={<Settings />} />
            <Route path="/teacher/lessons/:lessonId" element={<TeacherLessonDetail />} />
            <Route path="/teacher/students/:studentId/add-lesson" element={<AddLesson />} />
          </>
        ) : (
          <>
            <Route path="/" element={<Home />} />
            <Route path="/lessons" element={<Lessons />} />
            <Route path="/lessons/:lessonId" element={<LessonDetail />} />
            <Route path="/homework" element={<Homework />} />
            <Route path="/homework/:lessonId" element={<HomeworkDetail />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/materials" element={<Materials />} />
          </>
        )}
      </Routes>
    </BrowserRouter>
  );
}

export default App;
