import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../services/auth';

interface ProtectedRouteProps {
  children: JSX.Element;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { authed } = useAuth();
  const location = useLocation();

  if (!authed) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
