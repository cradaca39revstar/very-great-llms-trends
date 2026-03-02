import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { signIn, confirmSignIn } from 'aws-amplify/auth';

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [needNewPassword, setNeedNewPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const out = await signIn({
        username: email.trim(),
        password,
      });
      const next = (out as { nextStep?: { signInStep?: string } }).nextStep;
      if (next?.signInStep === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED' || (out as any).nextStep?.signInStep === 'CONFIRM_NEW_PASSWORD') {
        setNeedNewPassword(true);
        setLoading(false);
        return;
      }
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmNewPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await confirmSignIn({
        challengeResponse: newPassword,
      });
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (needNewPassword) {
    return (
      <div className="login-page">
        <h2 className="login-page__title">New password required</h2>
        <p className="login-page__subtitle">Set a new password to continue.</p>
        <form onSubmit={handleConfirmNewPassword}>
          <div className="login-page__form-group">
            <label htmlFor="new-password" className="login-page__label">New password</label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="login-page__input"
            />
          </div>
          {error && <p className="error" style={{ marginBottom: '1rem' }}>{error}</p>}
          <button type="submit" className="login-page__btn" disabled={loading}>Set password</button>
        </form>
      </div>
    );
  }

  return (
    <div className="login-page">
      <h2 className="login-page__title">Sign in</h2>
      <p className="login-page__subtitle">Trending Products – LLM report</p>
      <form onSubmit={handleSubmit}>
        <div className="login-page__form-group">
          <label htmlFor="email" className="login-page__label">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            className="login-page__input"
          />
        </div>
        <div className="login-page__form-group">
          <label htmlFor="password" className="login-page__label">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            className="login-page__input"
          />
        </div>
        {error && (
          <>
            <p className="error" style={{ marginBottom: '0.5rem' }}>{error}</p>
            {(error.toLowerCase().includes('incorrect') || error.toLowerCase().includes('username') || error.toLowerCase().includes('password')) && (
              <p className="meta" style={{ marginBottom: '1rem', fontSize: '0.875rem' }}>
                Si usas el usuario de prueba del script (<code>verygreat@test.com</code>), la contraseña es <strong>VeryGreat123!</strong> (V y G mayúsculas). Si el usuario fue creado con contraseña temporal, inicia sesión con esa contraseña primero; después podrás definir una nueva.
              </p>
            )}
          </>
        )}
        <button type="submit" className="login-page__btn" disabled={loading}>Sign in</button>
      </form>
    </div>
  );
}
