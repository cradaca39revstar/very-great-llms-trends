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
      <div style={{ maxWidth: 400, margin: '2rem auto', padding: '1rem' }}>
        <h2>New password required</h2>
        <p>Set a new password to continue.</p>
        <form onSubmit={handleConfirmNewPassword}>
          <div style={{ marginBottom: '1rem' }}>
            <label htmlFor="new-password">New password</label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              autoComplete="new-password"
              style={{ display: 'block', width: '100%', padding: '0.5rem' }}
            />
          </div>
          {error && <p className="error" style={{ marginBottom: '1rem' }}>{error}</p>}
          <button type="submit" disabled={loading}>Set password</button>
        </form>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 400, margin: '2rem auto', padding: '1rem' }}>
      <h2>Sign in</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            style={{ display: 'block', width: '100%', padding: '0.5rem' }}
          />
        </div>
        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            style={{ display: 'block', width: '100%', padding: '0.5rem' }}
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
        <button type="submit" disabled={loading}>Sign in</button>
      </form>
    </div>
  );
}
