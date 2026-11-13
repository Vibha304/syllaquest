import { Navigate, Route, Routes } from "react-router-dom";
import { useApp } from "./store";
import { Spinner } from "./components/ui";
import Layout from "./components/Layout";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Courses from "./pages/Courses";
import Course from "./pages/Course";
import Quiz from "./pages/Quiz";
import Achievements from "./pages/Achievements";
import Leaderboard from "./pages/Leaderboard";
import Subjects from "./pages/teacher/Subjects";
import Subject from "./pages/teacher/Subject";

export default function App() {
  const { user, ready } = useApp();
  if (!ready) return <Spinner label="Starting SyllaQuest…" />;
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Auth />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }
  const teacher = user.role === "teacher";
  return (
    <Routes>
      <Route path="/quiz/:sessionId" element={<Quiz />} />
      <Route element={<Layout />}>
        {teacher ? (
          <>
            <Route path="/" element={<Subjects />} />
            <Route path="/subjects/:id" element={<Subject />} />
          </>
        ) : (
          <>
            <Route path="/" element={<Dashboard />} />
            <Route path="/courses" element={<Courses />} />
            <Route path="/courses/:id" element={<Course />} />
            <Route path="/achievements" element={<Achievements />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
          </>
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
