import { Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { FolderOpen } from 'lucide-react';
import ProjectsPage from './pages/ProjectsPage';
import ProjectPage from './pages/ProjectPage';

export default function App() {
  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'Inter, sans-serif' }}>
      <nav style={navStyle}>
        <NavLink to="/" style={({ isActive }) => linkStyle(isActive)}>
          <FolderOpen size={20} />
          <span style={{ fontSize: 11 }}>Projects</span>
        </NavLink>
      </nav>
      <main style={{ flex: 1, overflow: 'hidden' }}>
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:id" element={<ProjectPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

const navStyle: React.CSSProperties = {
  width: 54,
  background: '#1e1e2e',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  paddingTop: 12,
  gap: 8,
};

const linkStyle = (active: boolean): React.CSSProperties => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: 2,
  color: active ? '#89b4fa' : '#6c7086',
  textDecoration: 'none',
  padding: 8,
  borderRadius: 6,
  transition: 'color .15s',
});
