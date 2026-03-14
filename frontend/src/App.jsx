import { useEffect, useState } from 'react'
import { Calendar, dateFnsLocalizer } from 'react-big-calendar'
import { format, getDay, parse, startOfWeek } from 'date-fns'
import { enUS } from 'date-fns/locale'
import 'react-big-calendar/lib/css/react-big-calendar.css'

const locales = {
  'en-US': enUS
}

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales
})

function App() {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(true)
  const [authUser, setAuthUser] = useState(null)
  const [calendars, setCalendars] = useState([])
  const [events, setEvents] = useState([])
  const [calendarLoading, setCalendarLoading] = useState(false)
  const [calendarError, setCalendarError] = useState('')
  const [calendarInfo, setCalendarInfo] = useState('')
  const [postLoading, setPostLoading] = useState(false)
  const [showAddCalendarForm, setShowAddCalendarForm] = useState(false)
  const [calendarSource, setCalendarSource] = useState('getlate')
  const [calendarName, setCalendarName] = useState('')
  const [calendarApiKey, setCalendarApiKey] = useState('')
  const [calendarProfileId, setCalendarProfileId] = useState('')
  const [calendarProfileName, setCalendarProfileName] = useState('')

  const activeCalendarIds = calendars
    .filter((calendarItem) => calendarItem.active)
    .map((calendarItem) => calendarItem.id)

  const visibleEvents = events.filter((eventItem) =>
    activeCalendarIds.includes(eventItem.calendarId)
  )

  const resetCalendarForm = () => {
    setCalendarSource('getlate')
    setCalendarName('')
    setCalendarApiKey('')
    setCalendarProfileId('')
    setCalendarProfileName('')
  }

  const fetchSession = async () => {
    const response = await fetch('/api/auth/me', {
      credentials: 'include'
    })
    const data = await response.json()
    setAuthUser(data.authenticated ? data.user : null)
  }

  const loadCalendars = async () => {
    setCalendarLoading(true)
    setCalendarError('')

    try {
      const response = await fetch('/api/calendars', {
        credentials: 'include'
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.error || 'Failed to load calendars')
      }

      const dbCalendars = (data.calendars || []).map((calendarItem) => ({
        id: calendarItem.id,
        name: calendarItem.name,
        source: calendarItem.source,
        active: calendarItem.is_active
      }))
      setCalendars(dbCalendars)
    } finally {
      setCalendarLoading(false)
    }
  }

  const toEventDate = (postItem) => {
    const startText = postItem.scheduled_for || postItem.published_at
    if (!startText) {
      return null
    }

    const start = new Date(startText)
    if (Number.isNaN(start.getTime())) {
      return null
    }

    const end = new Date(start.getTime() + 60 * 60 * 1000)
    return {
      id: postItem.id,
      title: postItem.title,
      start,
      end,
      calendarId: postItem.calendar_id
    }
  }

  const loadPosts = async () => {
    const response = await fetch('/api/posts', {
      credentials: 'include'
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || 'Failed to load posts')
    }

    const mappedEvents = (data.posts || [])
      .map((postItem) => toEventDate(postItem))
      .filter(Boolean)

    setEvents(mappedEvents)
  }

  const syncAndLoadPosts = async () => {
    setPostLoading(true)
    setCalendarError('')

    try {
      const response = await fetch('/api/posts/sync', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ debug: true })
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.error || 'Failed to sync posts')
      }

      const syncData = await response.json()
      console.log('Sync debug results:', syncData)
      const syncErrors = (syncData.results || []).filter((resultItem) => resultItem.error)
      if (syncErrors.length > 0) {
        setCalendarError(`Sync completed with ${syncErrors.length} calendar error(s)`)
      }
    } catch (syncError) {
      setCalendarError(syncError.message || 'Failed to sync posts')
    }

    try {
      await loadPosts()
    } catch (loadError) {
      setCalendarError(loadError.message || 'Failed to load posts')
    } finally {
      setPostLoading(false)
    }
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

  useEffect(() => {
    if (!authUser) {
      setCalendars([])
      setEvents([])
      return
    }

    loadCalendars()
      .then(() => syncAndLoadPosts())
      .catch((err) => {
        setCalendarLoading(false)
        setPostLoading(false)
        setCalendarError(err.message)
      })
  }, [authUser])

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
    setShowAddCalendarForm(false)
    resetCalendarForm()
  }

  const toggleCalendar = (calendarId) => {
    setCalendars((previousCalendars) =>
      previousCalendars.map((calendarItem) =>
        calendarItem.id === calendarId
          ? { ...calendarItem, active: !calendarItem.active }
          : calendarItem
      )
    )
  }

  const handleCreateCalendar = async (event) => {
    event.preventDefault()
    setCalendarError('')
    setCalendarInfo('')

    const payload = {
      source: calendarSource,
      api_key: calendarApiKey,
      name: calendarName || undefined
    }

    if (calendarSource === 'getlate') {
      payload.profile_id = calendarProfileId
      payload.profile_name = calendarProfileName || undefined
    }

    const response = await fetch('/api/calendars', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })

    const data = await response.json()
    if (!response.ok) {
      setCalendarError(data.error || 'Failed to create calendar')
      return
    }

    setCalendarInfo('Calendar created successfully')
    await loadCalendars()
    await syncAndLoadPosts()
    setShowAddCalendarForm(false)
    resetCalendarForm()
  }

  if (loading) {
    return (
      <main className="container auth-screen">
        <h1>YaLate</h1>
        <p>Loading session...</p>
      </main>
    )
  }

  if (authUser) {
    return (
      <main className="dashboard-screen">
        <aside className="calendar-sidebar">
          <div>
            <h1>YaLate</h1>
            <p className="sidebar-subtitle">{authUser.email}</p>
          </div>

          <section className="calendar-controls">
            <div className="sidebar-section-header">
              <h2>Calendars</h2>
              <div className="sidebar-actions">
                <button
                  className="tab-btn"
                  type="button"
                  onClick={syncAndLoadPosts}
                  disabled={postLoading}
                >
                  Sync Posts
                </button>
                <button
                  className="primary-btn"
                  type="button"
                  onClick={() => setShowAddCalendarForm((previousValue) => !previousValue)}
                >
                  Add Calendar
                </button>
              </div>
            </div>

            {showAddCalendarForm ? (
              <form className="add-calendar-form" onSubmit={handleCreateCalendar}>
                <label>
                  Source
                  <select
                    value={calendarSource}
                    onChange={(event) => setCalendarSource(event.target.value)}
                  >
                    <option value="getlate">GetLate</option>
                    <option value="ghost_blog">Ghost Blog</option>
                  </select>
                </label>

                <label>
                  API Key
                  <input
                    type="password"
                    value={calendarApiKey}
                    onChange={(event) => setCalendarApiKey(event.target.value)}
                    required
                  />
                </label>

                <label>
                  Calendar Name (optional)
                  <input
                    type="text"
                    value={calendarName}
                    onChange={(event) => setCalendarName(event.target.value)}
                  />
                </label>

                {calendarSource === 'getlate' ? (
                  <>
                    <label>
                      Profile ID
                      <input
                        type="text"
                        value={calendarProfileId}
                        onChange={(event) => setCalendarProfileId(event.target.value)}
                        required
                      />
                    </label>
                    <label>
                      Profile Name (optional)
                      <input
                        type="text"
                        value={calendarProfileName}
                        onChange={(event) => setCalendarProfileName(event.target.value)}
                      />
                    </label>
                  </>
                ) : null}

                <div className="add-calendar-actions">
                  <button className="primary-btn" type="submit">
                    Save
                  </button>
                  <button
                    className="tab-btn"
                    type="button"
                    onClick={() => {
                      setShowAddCalendarForm(false)
                      resetCalendarForm()
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            ) : null}

            {calendarLoading ? <p className="calendar-meta">Loading calendars...</p> : null}
            {postLoading ? <p className="calendar-meta">Syncing and loading posts...</p> : null}
            {calendarInfo ? <p className="calendar-success">{calendarInfo}</p> : null}
            {calendarError ? <p className="calendar-error">{calendarError}</p> : null}

            <ul className="calendar-list">
              {calendars.length === 0 ? <li className="calendar-meta">No calendars found.</li> : null}
              {calendars.map((calendarItem) => (
                <li key={calendarItem.id}>
                  <label className="calendar-toggle">
                    <input
                      type="checkbox"
                      checked={calendarItem.active}
                      onChange={() => toggleCalendar(calendarItem.id)}
                    />
                    <span>{calendarItem.name}</span>
                    <small className="calendar-source">{calendarItem.source}</small>
                  </label>
                </li>
              ))}
            </ul>
          </section>

          <button className="tab-btn" type="button" onClick={handleLogout}>
            Logout
          </button>
        </aside>

        <section className="calendar-main">
          <Calendar
            localizer={localizer}
            events={visibleEvents}
            startAccessor="start"
            endAccessor="end"
            views={["month", "week", "day", "agenda"]}
            defaultView="month"
            popup
          />
        </section>
      </main>
    )
  }

  return (
    <main className="container auth-screen">
      <h1>YaLate</h1>

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

      {info ? <p className="info-text">{info}</p> : null}
      {error ? <p className="error-text">Error: {error}</p> : null}
    </main>
  )
}

export default App
