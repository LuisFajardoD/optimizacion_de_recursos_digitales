import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ConfirmModal } from './ConfirmModal';
import { useAuth } from '../services/auth';
import { useI18n } from '../services/i18n';

export function LogoutButton() {
  const { logout } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  return (
    <>
      <button className="ghost" type="button" onClick={() => setOpen(true)}>
        {t.logout}
      </button>
      <ConfirmModal
        open={open}
        title={t.logoutTitle}
        message={t.logoutMessage}
        confirmText={t.logoutConfirm}
        cancelText={t.cancel}
        danger
        onCancel={() => setOpen(false)}
        onConfirm={() => {
          logout();
          setOpen(false);
          navigate('/login');
        }}
      />
    </>
  );
}
