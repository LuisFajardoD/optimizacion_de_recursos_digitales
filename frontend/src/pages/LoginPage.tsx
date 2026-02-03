import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth, isAuthenticated } from '../services/auth';
import { useI18n } from '../services/i18n';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const { t } = useI18n();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [username, setUsername] = useState('proyectoVIII');
  const [password, setPassword] = useState('Admin');
  const [remember, setRemember] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [logoSrc, setLogoSrc] = useState(() => {
    const isLight = document.documentElement.classList.contains('theme-light');
    return isLight ? '/src/assets/udg/udg-logo-light.png' : '/src/assets/udg/udg-logo-dark.png';
  });

  useEffect(() => {
    if (isAuthenticated()) {
      navigate('/', { replace: true });
    }
  }, [navigate]);

  const themeLogo = useMemo(() => logoSrc, [logoSrc]);

  useEffect(() => {
    const updateLogo = () => {
      const isLight = document.documentElement.classList.contains('theme-light');
      setLogoSrc(isLight ? '/src/assets/udg/udg-logo-light.png' : '/src/assets/udg/udg-logo-dark.png');
    };
    updateLogo();
    const observer = new MutationObserver(updateLogo);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let animationId = 0;
    const mouse = { x: 0, y: 0, active: false };
    const theme = { light: document.documentElement.classList.contains('theme-light') };
    const particles: {
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
    }[] = [];

    const updateTheme = () => {
      theme.light = document.documentElement.classList.contains('theme-light');
    };

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      width = rect?.width ?? window.innerWidth;
      height = rect?.height ?? window.innerHeight;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      particles.length = 0;
      const count = Math.min(90, Math.max(40, Math.floor((width * height) / 14000)));
      for (let i = 0; i < count; i += 1) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.6,
          vy: (Math.random() - 0.5) * 0.6,
          size: 2 + Math.random() * 3,
        });
      }
    };

    const onMove = (event: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = event.clientX - rect.left;
      mouse.y = event.clientY - rect.top;
      mouse.active = true;
    };

    const onLeave = () => {
      mouse.active = false;
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      const lineColor = theme.light ? 'rgba(60, 120, 110, 0.18)' : 'rgba(130, 225, 168, 0.18)';
      const dotColor = theme.light ? 'rgba(60, 120, 110, 0.55)' : 'rgba(221, 221, 221, 0.6)';

      for (let i = 0; i < particles.length; i += 1) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;

        if (mouse.active) {
          const dx = p.x - mouse.x;
          const dy = p.y - mouse.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 140) {
            const force = (140 - dist) / 140;
            p.vx += (dx / dist) * force * 0.08;
            p.vy += (dy / dist) * force * 0.08;
            ctx.strokeStyle = theme.light ? 'rgba(60, 120, 110, 0.35)' : 'rgba(241, 193, 110, 0.35)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(mouse.x, mouse.y);
            ctx.stroke();
          }
        }

        ctx.fillStyle = dotColor;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();

        for (let j = i + 1; j < particles.length; j += 1) {
          const q = particles[j];
          const dx = p.x - q.x;
          const dy = p.y - q.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 140) {
            ctx.strokeStyle = lineColor;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.stroke();
          }
        }
      }

      animationId = window.requestAnimationFrame(draw);
    };

    const observer = new MutationObserver(updateTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

    resize();
    draw();
    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseleave', onLeave);

    return () => {
      window.cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseleave', onLeave);
      observer.disconnect();
    };
  }, []);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    const result = login(username.trim(), password, remember);
    if (!result.ok) {
      setError(t.loginError);
      setLoading(false);
      return;
    }

    const redirect = (location.state as { from?: string } | null)?.from ?? '/';
    navigate(redirect, { replace: true });
  };

  return (
    <section className="login-page">
      <div className="login-particles">
        <canvas ref={canvasRef} />
      </div>
      <div className="login-content">
        <div className="login-grid">
        <div className="login-branding">
          <img className="login-logo" src={themeLogo} alt="UDG" />
          <span className="login-eyebrow">{t.loginEyebrow}</span>
          <h1>{t.loginTitle}</h1>
          <p className="login-subtitle">{t.loginSubtitle}</p>

          <div className="login-panel">
            <h3>{t.loginPanelTitle}</h3>
            <ul>
              <li>{t.loginBulletBatch}</li>
              <li>{t.loginBulletPresets}</li>
              <li>{t.loginBulletCrop}</li>
              <li>{t.loginBulletAdjust}</li>
              <li>{t.loginBulletZip}</li>
            </ul>
          </div>

          <div className="login-footer">
            <div>{t.loginFooterSubject}</div>
            <div>{t.loginFooterAdvisor}</div>
            <div>{t.loginFooterTeam}</div>
            <div>{t.loginFooterMember1}</div>
            <div>{t.loginFooterMember2}</div>
            <div>{t.loginFooterMember3}</div>
            <div>{t.loginFooterMember4}</div>
            <div>{t.loginFooterYear.replace('{year}', String(new Date().getFullYear()))}</div>
          </div>
        </div>

        <div className="login-form-card">
          <h2>{t.loginFormTitle}</h2>
          <p className="muted">{t.loginFormSubtitle}</p>

          <form className="login-form" onSubmit={onSubmit}>
            <label>
              {t.loginUserLabel}
              <input
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
              />
            </label>
            <span className="login-hint">
              {t.loginHintUser}
            </span>

            <label>
              {t.loginPassLabel}
              <div className="password-field">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="ghost"
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? t.loginHide : t.loginShow}
                </button>
              </div>
            </label>
            <span className="login-hint">
              {t.loginHintPass}
            </span>

            <label className="login-remember">
              <input
                type="checkbox"
                checked={remember}
                onChange={(event) => setRemember(event.target.checked)}
              />
              {t.loginRemember}
            </label>

            {error && <div className="login-error">{error}</div>}

            <button className="primary" type="submit" disabled={loading}>
              {loading ? t.loginLoading : t.loginButton}
            </button>

            <button className="link-button" type="button">
              {t.loginHelp}
            </button>
          </form>

          <div className="login-demo-info">
            <span>{t.loginDemoUser}</span>
            <span>{t.loginDemoPass}</span>
          </div>
        </div>
        </div>
      </div>
    </section>
  );
}
