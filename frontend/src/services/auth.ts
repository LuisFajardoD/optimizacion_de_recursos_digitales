import { useEffect, useState } from 'react';

const STORAGE_KEY = 'demo_auth';

type AuthPayload = {
  token: string;
  timestamp: number;
  remember: boolean;
};

type AuthListener = () => void;

const listeners = new Set<AuthListener>();

function notify() {
  listeners.forEach((listener) => listener());
}

export function isAuthenticated(): boolean {
  return Boolean(localStorage.getItem(STORAGE_KEY));
}

export function loginDemo(username: string, password: string, remember: boolean) {
  if (username !== 'proyectoVIII' || password !== 'Admin') {
    return { ok: false, error: 'invalid' as const };
  }

  const payload: AuthPayload = {
    token: 'demo-token',
    timestamp: Date.now(),
    remember,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  notify();
  return { ok: true as const };
}

export function logout() {
  localStorage.removeItem(STORAGE_KEY);
  notify();
}

export function subscribeAuth(listener: AuthListener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useAuth() {
  const [authed, setAuthed] = useState(isAuthenticated());

  useEffect(() => {
    const unsubscribe = subscribeAuth(() => setAuthed(isAuthenticated()));
    return unsubscribe;
  }, []);

  return {
    authed,
    login: loginDemo,
    logout,
  };
}
