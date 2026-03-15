import { useEffect, useMemo, useState } from 'react'
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

const SOURCE_LABELS = {
  ghost_blog: 'Ghost Blog',
  getlate: 'Late'
}

const TYPE_LABEL_OVERRIDES = {
  'email-only': 'Email',
  linkedin: 'Linked In',
  'multi-platform': 'Multi Platform'
}

const DISTINCT_COLOR_PALETTE = [
  '#2563eb',
  '#4c4c4c',
  '#16a34a',
  '#7c3aed',
  '#ff0000',
  '#0891b2',
  '#000000',
  '#faab00',
  '#0f766e',
  '#ff00ee',
  '#059669',
  '#c2410c',
  '#0e7490',
  '#b91c1c',
  '#1d4ed8',
  '#15803d',
  '#9333ea',
  '#0369a1',
  '#a16207',
  '#be185d',
  '#334155',
  '#0284c7',
  '#d97706',
  '#7e22ce'
]

const toSlug = (value) =>
  String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')

const toTypeKind = (postItem) => {
  if (postItem.post_type_slug) {
    return toSlug(postItem.post_type_slug)
  }
  if (postItem.post_type_name) {
    return toSlug(postItem.post_type_name)
  }
  return 'post'
}

const toTypeLabel = (kind) => {
  if (TYPE_LABEL_OVERRIDES[kind]) {
    return TYPE_LABEL_OVERRIDES[kind]
  }
  return kind
    .split('-')
    .filter(Boolean)
    .map((chunk) => chunk[0].toUpperCase() + chunk.slice(1))
    .join(' ')
}

const hashString = (value) => {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  }
  return hash
}

const getLegendKey = (calendarId, cardKind) => `${calendarId}:${cardKind}`

const getLegendFallbackColor = (calendarId, cardKind) => {
  const hashed = hashString(getLegendKey(calendarId, cardKind))
  return DISTINCT_COLOR_PALETTE[hashed % DISTINCT_COLOR_PALETTE.length]
}

const EVENT_PREVIEW_LENGTH = 18

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
  const [calendarBlogUrl, setCalendarBlogUrl] = useState('')
  const [credentialCheckLoading, setCredentialCheckLoading] = useState(false)
  const [editingCalendarId, setEditingCalendarId] = useState(null)
  const [editCalendarName, setEditCalendarName] = useState('')
  const [editCalendarApiKey, setEditCalendarApiKey] = useState('')
  const [editCalendarProfileId, setEditCalendarProfileId] = useState('')
  const [editCalendarProfileName, setEditCalendarProfileName] = useState('')
  const [editCalendarBlogUrl, setEditCalendarBlogUrl] = useState('')
  const [visibleLegendKeys, setVisibleLegendKeys] = useState({})

  const calendarTypeCounts = events.reduce((accumulator, eventItem) => {
    const calendarId = eventItem.calendarId
    const kind = eventItem.cardKind || 'post'
    if (!accumulator[calendarId]) {
      accumulator[calendarId] = {}
    }
    accumulator[calendarId][kind] = (accumulator[calendarId][kind] || 0) + 1
    return accumulator
  }, {})

  const legendColorByKey = useMemo(() => {
    const assigned = {}
    let paletteIndex = 0

    const orderedCalendarIds = calendars
      .map((calendarItem) => String(calendarItem.id))
      .filter((calendarId) => Boolean(calendarTypeCounts[calendarId]))

    orderedCalendarIds.forEach((calendarId) => {
      const typeCounts = calendarTypeCounts[calendarId]
      const sortedKinds = Object.keys(typeCounts).sort((left, right) => left.localeCompare(right))
      sortedKinds.forEach((kind) => {
        assigned[getLegendKey(calendarId, kind)] =
          DISTINCT_COLOR_PALETTE[paletteIndex % DISTINCT_COLOR_PALETTE.length]
        paletteIndex += 1
      })
    })

    return assigned
  }, [calendarTypeCounts, calendars])

  const getLegendColor = (calendarId, cardKind) =>
    legendColorByKey[getLegendKey(calendarId, cardKind)] ||
    getLegendFallbackColor(calendarId, cardKind)

  const visibleEvents = events.filter((eventItem) => {
    const legendKey = getLegendKey(eventItem.calendarId, eventItem.cardKind)
    return visibleLegendKeys[legendKey] !== false
  })

  const resetCalendarForm = () => {
    setCalendarSource('getlate')
    setCalendarName('')
    setCalendarApiKey('')
    setCalendarProfileId('')
    setCalendarProfileName('')
    setCalendarBlogUrl('')
    setCredentialCheckLoading(false)
  }

  const resetEditCalendarForm = () => {
    setEditingCalendarId(null)
    setEditCalendarName('')
    setEditCalendarApiKey('')
    setEditCalendarProfileId('')
    setEditCalendarProfileName('')
    setEditCalendarBlogUrl('')
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
        active: calendarItem.is_active,
        sourceProfileId: calendarItem.source_profile_id,
        sourceProfileName: calendarItem.source_profile_name
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
    const cardKind = toTypeKind(postItem)
    return {
      id: postItem.id,
      title: postItem.title,
      start,
      end,
      calendarId: postItem.calendar_id,
      postTypeName: postItem.post_type_name,
      postTypeSlug: postItem.post_type_slug,
      status: postItem.status,
      cardKind
    }
  }

  const truncateTitle = (value, maxLength = EVENT_PREVIEW_LENGTH) => {
    if (!value || value.length <= maxLength) {
      return value
    }
    return `${value.slice(0, maxLength)}…`
  }

  const toTooltipDate = (dateValue) => {
    if (!(dateValue instanceof Date) || Number.isNaN(dateValue.getTime())) {
      return 'Unknown date'
    }
    return dateValue.toLocaleString()
  }

  const buildEventTooltip = (event) => {
    const lines = [
      event.title || 'Untitled',
      `Type: ${toTypeLabel(event.cardKind)}`,
      `Status: ${event.status || 'unknown'}`,
      `Start: ${toTooltipDate(event.start)}`
    ]
    return lines.join('\n')
  }

  const eventPropGetter = (eventItem) => {
    const eventColor = getLegendColor(eventItem.calendarId, eventItem.cardKind)
    return {
      style: {
        backgroundColor: eventColor,
        borderColor: eventColor
      }
    }
  }

  const EventCardContent = ({ event }) => {
    const badgeText = toTypeLabel(event.cardKind)
    return (
      <div className="event-card-content">
        <strong>{badgeText}:</strong> {truncateTitle(event.title)}
      </div>
    )
  }

  const toggleLegendVisibility = (calendarId, cardKind) => {
    const legendKey = getLegendKey(calendarId, cardKind)
    setVisibleLegendKeys((previous) => ({
      ...previous,
      [legendKey]: previous[legendKey] === false
    }))
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

  const syncAndLoadPosts = async (calendarId = null) => {
    setPostLoading(true)
    setCalendarError('')

    try {
      const response = await fetch('/api/posts/sync', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          debug: true,
          calendar_id: calendarId || undefined
        })
      })

      const syncData = await response.json()
      if (response.status !== 200 && response.status !== 207) {
        throw new Error(syncData.error || 'Failed to sync posts')
      }

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
      setVisibleLegendKeys({})
      return
    }

    loadCalendars()
      .then(() => loadPosts())
      .catch((err) => {
        setCalendarLoading(false)
        setPostLoading(false)
        setCalendarError(err.message)
      })
  }, [authUser])

  useEffect(() => {
    setVisibleLegendKeys((previous) => {
      const next = { ...previous }
      events.forEach((eventItem) => {
        const legendKey = getLegendKey(eventItem.calendarId, eventItem.cardKind)
        if (next[legendKey] === undefined) {
          next[legendKey] = true
        }
      })
      return next
    })
  }, [events])

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
    resetEditCalendarForm()
  }

  const validateCalendarPayload = async (payload) => {
    setCredentialCheckLoading(true)

    try {
      const response = await fetch('/api/calendars/validate', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      })

      const data = await response.json()
      if (!response.ok || !data.valid) {
        throw new Error(data.error || 'Credential check failed')
      }

      return data
    } finally {
      setCredentialCheckLoading(false)
    }
  }

  const handleCheckCredentials = async () => {
    setCalendarError('')
    setCalendarInfo('')

    const payload = {
      source: calendarSource,
      api_key: calendarApiKey
    }

    if (calendarSource === 'getlate') {
      payload.profile_id = calendarProfileId
    }

    if (calendarSource === 'ghost_blog') {
      payload.blog_url = calendarBlogUrl
    }

    try {
      await validateCalendarPayload(payload)
      setCalendarInfo('Credentials validated successfully')
    } catch (checkError) {
      setCalendarError(checkError.message || 'Credential check failed')
    }
  }

  const startEditCalendar = (calendarItem) => {
    setEditingCalendarId(calendarItem.id)
    setEditCalendarName(calendarItem.name || '')
    setEditCalendarApiKey('')

    if (calendarItem.source === 'getlate') {
      setEditCalendarProfileId(calendarItem.sourceProfileId || '')
      setEditCalendarProfileName(calendarItem.sourceProfileName || '')
      setEditCalendarBlogUrl('')
      return
    }

    if (calendarItem.source === 'ghost_blog') {
      setEditCalendarBlogUrl(calendarItem.sourceProfileId || '')
      setEditCalendarProfileId('')
      setEditCalendarProfileName('')
      return
    }

    setEditCalendarProfileId('')
    setEditCalendarProfileName('')
    setEditCalendarBlogUrl('')
  }

  const handleUpdateCalendar = async (event, calendarItem) => {
    event.preventDefault()
    setCalendarError('')
    setCalendarInfo('')

    const payload = {
      name: editCalendarName
    }

    if (editCalendarApiKey.trim()) {
      payload.api_key = editCalendarApiKey.trim()
    }

    if (calendarItem.source === 'getlate') {
      payload.profile_id = editCalendarProfileId
      payload.profile_name = editCalendarProfileName || undefined
    }

    if (calendarItem.source === 'ghost_blog') {
      payload.blog_url = editCalendarBlogUrl
    }

    const response = await fetch(`/api/calendars/${calendarItem.id}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })

    const data = await response.json()
    if (!response.ok) {
      setCalendarError(data.error || 'Failed to update calendar')
      return
    }

    setCalendarInfo('Calendar updated successfully')
    resetEditCalendarForm()
    await loadCalendars()
    await syncAndLoadPosts(calendarItem.id)
  }

  const handleDeleteCalendar = async (calendarItem) => {
    const shouldDelete = window.confirm(
      `Delete calendar "${calendarItem.name}"? This also removes synced posts.`
    )
    if (!shouldDelete) {
      return
    }

    setCalendarError('')
    setCalendarInfo('')

    const response = await fetch(`/api/calendars/${calendarItem.id}`, {
      method: 'DELETE',
      credentials: 'include'
    })

    const data = await response.json()
    if (!response.ok) {
      setCalendarError(data.error || 'Failed to delete calendar')
      return
    }

    setCalendarInfo('Calendar deleted successfully')
    if (editingCalendarId === calendarItem.id) {
      resetEditCalendarForm()
    }
    await loadCalendars()
    await loadPosts()
  }

  const handleSyncCalendar = async (calendarItem) => {
    await syncAndLoadPosts(calendarItem.id)
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

    if (calendarSource === 'ghost_blog') {
      payload.blog_url = calendarBlogUrl
    }

    try {
      await validateCalendarPayload(payload)
    } catch (checkError) {
      setCalendarError(checkError.message || 'Credential check failed')
      return
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
    const newCalendarId = data.calendar?.id || null
    await loadCalendars()
    await syncAndLoadPosts(newCalendarId)
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
                    <option value="getlate">Late</option>
                    <option value="ghost_blog">Ghost Blog</option>
                  </select>
                </label>

                <label>
                  {calendarSource === 'ghost_blog' ? 'API Key (Content or Admin)' : 'API Key'}
                  <input
                    type="password"
                    value={calendarApiKey}
                    onChange={(event) => setCalendarApiKey(event.target.value)}
                    required
                  />
                </label>

                {calendarSource === 'ghost_blog' ? (
                  <p className="calendar-meta">
                    Use Admin API key (`id:secret`) to include scheduled and email-only items.
                  </p>
                ) : null}

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

                {calendarSource === 'ghost_blog' ? (
                  <label>
                    Blog URL
                    <input
                      type="url"
                      value={calendarBlogUrl}
                      onChange={(event) => setCalendarBlogUrl(event.target.value)}
                      placeholder="https://your-blog.example"
                      required
                    />
                  </label>
                ) : null}

                <div className="add-calendar-actions">
                  <button
                    className="tab-btn"
                    type="button"
                    onClick={handleCheckCredentials}
                    disabled={credentialCheckLoading}
                  >
                    Check Credentials
                  </button>
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
                  <div className="calendar-header-row">
                    <span className="calendar-title-line">
                      {calendarItem.name} - {SOURCE_LABELS[calendarItem.source] || calendarItem.source}
                    </span>
                    <div className="calendar-item-actions">
                      <button
                        className="icon-btn"
                        type="button"
                        onClick={() => handleSyncCalendar(calendarItem)}
                        aria-label="Sync calendar"
                        title="Sync calendar"
                        disabled={postLoading}
                      >
                        🔄
                      </button>
                      <button
                        className="icon-btn"
                        type="button"
                        onClick={() => startEditCalendar(calendarItem)}
                        aria-label="Edit calendar"
                        title="Edit calendar"
                      >
                        ✏️
                      </button>
                      <button
                        className="icon-btn"
                        type="button"
                        onClick={() => handleDeleteCalendar(calendarItem)}
                        aria-label="Delete calendar"
                        title="Delete calendar"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>

                  <div className="calendar-legend-list">
                    {Object.entries(calendarTypeCounts[calendarItem.id] || {})
                      .sort((left, right) => left[0].localeCompare(right[0]))
                      .map(([kind, count]) => {
                        const legendKey = getLegendKey(calendarItem.id, kind)
                        const legendColor = getLegendColor(calendarItem.id, kind)
                        return (
                          <label className="legend-row" key={legendKey}>
                            <span className="legend-chip" style={{ backgroundColor: legendColor }} />
                            <span>{toTypeLabel(kind)}</span>
                            <small>{count}</small>
                            <input
                              type="checkbox"
                              checked={visibleLegendKeys[legendKey] !== false}
                              onChange={() => toggleLegendVisibility(calendarItem.id, kind)}
                            />
                          </label>
                        )
                      })}
                  </div>

                  {editingCalendarId === calendarItem.id ? (
                    <form
                      className="add-calendar-form calendar-edit-form"
                      onSubmit={(event) => handleUpdateCalendar(event, calendarItem)}
                    >
                      <label>
                        Name
                        <input
                          type="text"
                          value={editCalendarName}
                          onChange={(event) => setEditCalendarName(event.target.value)}
                          required
                        />
                      </label>

                      {calendarItem.source === 'getlate' ? (
                        <>
                          <label>
                            Profile ID
                            <input
                              type="text"
                              value={editCalendarProfileId}
                              onChange={(event) => setEditCalendarProfileId(event.target.value)}
                              required
                            />
                          </label>
                          <label>
                            Profile Name (optional)
                            <input
                              type="text"
                              value={editCalendarProfileName}
                              onChange={(event) => setEditCalendarProfileName(event.target.value)}
                            />
                          </label>
                        </>
                      ) : null}

                      {calendarItem.source === 'ghost_blog' ? (
                        <label>
                          Blog URL
                          <input
                            type="url"
                            value={editCalendarBlogUrl}
                            onChange={(event) => setEditCalendarBlogUrl(event.target.value)}
                            required
                          />
                        </label>
                      ) : null}

                      <label>
                        API Key (optional, rotate to Content or Admin key)
                        <input
                          type="password"
                          value={editCalendarApiKey}
                          onChange={(event) => setEditCalendarApiKey(event.target.value)}
                        />
                      </label>

                      <div className="add-calendar-actions">
                        <button className="primary-btn" type="submit">
                          Update
                        </button>
                        <button className="tab-btn" type="button" onClick={resetEditCalendarForm}>
                          Cancel
                        </button>
                      </div>
                    </form>
                  ) : null}
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
            tooltipAccessor={(event) => buildEventTooltip(event)}
            eventPropGetter={eventPropGetter}
            components={{ event: EventCardContent }}
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
