import { useEffect, useState } from 'react'

function App() {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(true)
  const [authUser, setAuthUser] = useState(null)

  const fetchSession = async () => {
    const response = await fetch('/api/auth/me', {
      credentials: 'include'
    })
    const data = await response.json()
    setAuthUser(data.authenticated ? data.user : null)
  }

  useEffect(() => {
    fetchSession()
      .catch(() => {
        setError('Failed to load session state')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setInfo('')

    const endpoint = mode === 'signup' ? '/api/auth/signup' : '/api/auth/login'
    const body =
      mode === 'signup'
        ? { email, password, display_name: displayName }
        : { email, password }

    const response = await fetch(endpoint, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    })

    const data = await response.json()

    if (!response.ok) {
      setError(data.error || 'Authentication failed')
      return
    }

    setInfo(data.message || 'Success')
    setPassword('')
    await fetchSession()
  }

  const handleLogout = async () => {
    setError('')
    setInfo('')

    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include'
    })

    const data = await response.json()
    if (!response.ok) {
      setError(data.error || 'Logout failed')
      return
    }

    setInfo(data.message || 'Logged out')
    setAuthUser(null)
  }

  if (loading) {
    return (
      <main className="container">
        <h1>YaLate</h1>
        <p>Loading session...</p>
      </main>
    )
  }

  return (
    <main className="container">
      <h1>YaLate</h1>

      {authUser ? (
        <section className="auth-panel">
          <p className="auth-title">You are logged in</p>
          <p>Email: {authUser.email}</p>
          <p>Name: {authUser.display_name || 'Not set'}</p>
          <button className="primary-btn" type="button" onClick={handleLogout}>
            Logout
          </button>
        </section>
      ) : (
        <section className="auth-panel">
          <div className="mode-switch">
            <button
              className={mode === 'login' ? 'tab-btn active' : 'tab-btn'}
              type="button"
              onClick={() => setMode('login')}
            >
              Login
            </button>
            <button
              className={mode === 'signup' ? 'tab-btn active' : 'tab-btn'}
              type="button"
              onClick={() => setMode('signup')}
            >
              Sign Up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {mode === 'signup' ? (
              <label>
                Display Name
                <input
                  type="text"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Your name"
                />
              </label>
            ) : null}

            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                required
              />
            </label>

            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter password"
                required
              />
            </label>

            <button className="primary-btn" type="submit">
              {mode === 'signup' ? 'Create Account' : 'Login'}
            </button>
          </form>
        </section>
      )}

      {info ? <p className="info-text">{info}</p> : null}
      {error ? <p className="error-text">Error: {error}</p> : null}
    </main>
  )
}

export default App
