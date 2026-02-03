import { useEffect } from 'react';
import { Link, NavLink, Route, Routes } from 'react-router-dom';

import './App.css';
import { LogoutButton } from './components/LogoutButton';
import { ProtectedRoute } from './components/ProtectedRoute';
import { JobDetailPage } from './pages/JobDetailPage';
import { JobsPage } from './pages/JobsPage';
import { LoginPage } from './pages/LoginPage';
import { SettingsPage } from './pages/SettingsPage';
import { UploadPage } from './pages/UploadPage';
import { useAuth } from './services/auth';
import { useI18n } from './services/i18n';

function App() {
  const { t } = useI18n();
  const { authed } = useAuth();

  useEffect(() => {
    const theme = localStorage.getItem('theme') || 'dark';
    const root = document.documentElement;
    if (theme === 'light') {
      root.classList.add('theme-light');
      root.classList.remove('theme-dark');
    } else {
      root.classList.add('theme-dark');
      root.classList.remove('theme-light');
    }
  }, []);

  return (
    <div className="app">
      {authed && (
        <nav className="top-nav">
          <Link className="brand-link" to="/">
            <span>Proyecto VIII</span>
            <strong>Optimizador Digital</strong>
          </Link>
          <div className="nav-actions">
            <div className="nav-links">
              <NavLink to="/" end>
                {t.navUpload}
              </NavLink>
              <NavLink to="/jobs">{t.navJobs}</NavLink>
              <NavLink to="/configuracion">{t.navSettings}</NavLink>
            </div>
            <LogoutButton />
          </div>
        </nav>
      )}

      <main>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <UploadPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/jobs"
            element={
              <ProtectedRoute>
                <JobsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/jobs/:id"
            element={
              <ProtectedRoute>
                <JobDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/configuracion"
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

export default App;
