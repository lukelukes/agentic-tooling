---
name: bubbletea
description: >
  Guide for building Go TUI applications with Bubbletea (Charm's Elm Architecture framework),
  Bubbles components, and Lipgloss styling. Use this skill whenever the user is building a
  terminal UI in Go, working with Bubbletea models/messages/commands, composing Bubbles
  components (list, table, viewport, textinput, spinner), styling with Lipgloss, or asking
  about TUI architecture patterns. Also trigger when you see imports of bubbletea, bubbles,
  or lipgloss packages, or when the user mentions "tea.Model", "tea.Cmd", "tea.Msg",
  or "charm" in a Go TUI context.
---

# Building Bubbletea Programs

Bubbletea is a Go framework for building terminal UIs based on The Elm Architecture. Programs are structured around three concepts: a **Model** (state), an **Update** function (handles events), and a **View** function (renders UI). This functional, message-driven design keeps state management predictable even as applications grow complex.

## The Core Loop

Every Bubbletea program implements `tea.Model`:

```go
type model struct {
    items    []string
    cursor   int
    selected map[int]struct{}
}

func (m model) Init() tea.Cmd {
    return nil // or return a command to run on startup
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyPressMsg:
        switch msg.String() {
        case "ctrl+c", "q":
            return m, tea.Quit
        case "up", "k":
            if m.cursor > 0 {
                m.cursor--
            }
        case "down", "j":
            if m.cursor < len(m.items)-1 {
                m.cursor++
            }
        case "enter":
            if _, ok := m.selected[m.cursor]; ok {
                delete(m.selected, m.cursor)
            } else {
                m.selected[m.cursor] = struct{}{}
            }
        }
    }
    return m, nil
}

func (m model) View() string {
    var b strings.Builder
    for i, item := range m.items {
        cursor := "  "
        if i == m.cursor {
            cursor = "> "
        }
        checked := " "
        if _, ok := m.selected[i]; ok {
            checked = "x"
        }
        fmt.Fprintf(&b, "%s [%s] %s\n", cursor, checked, item)
    }
    b.WriteString("\nPress q to quit.\n")
    return b.String()
}

func main() {
    p := tea.NewProgram(model{
        items:    []string{"Buy milk", "Fold laundry", "Build a TUI"},
        selected: make(map[int]struct{}),
    })
    if _, err := p.Run(); err != nil {
        fmt.Fprintf(os.Stderr, "Error: %v\n", err)
        os.Exit(1)
    }
}
```

## Messages and Commands

**Messages** (`tea.Msg`) are events — keypresses, mouse events, window resizes, timer ticks, or custom types returned from I/O. They flow into `Update()` via type switch.

**Commands** (`tea.Cmd`) are functions that perform I/O and return a message. They run asynchronously in goroutines managed by the framework. This is how Bubbletea keeps the event loop non-blocking.

```go
// A command is just a function that returns a message
func fetchData(url string) tea.Cmd {
    return func() tea.Msg {
        resp, err := http.Get(url)
        if err != nil {
            return errMsg{err}
        }
        defer resp.Body.Close()
        var data Response
        json.NewDecoder(resp.Body).Decode(&data)
        return dataMsg{data}
    }
}

// Handle the result in Update
case dataMsg:
    m.data = msg.data
    m.loading = false
case errMsg:
    m.err = msg.err
    m.loading = false
```

**Batching and sequencing commands:**

```go
// Concurrent — no ordering guarantees
return m, tea.Batch(fetchUsers, fetchPosts, m.spinner.Tick)

// Sequential — guaranteed order
return m, tea.Sequence(validateCmd, saveCmd, notifyCmd)
```

## Parent/Child Model Composition

For anything beyond a trivial app, break the UI into child models. The parent routes messages and composes views.

```go
type rootModel struct {
    sidebar sidebarModel
    content contentModel
    status  statusModel
    focused int // which child has focus
    width   int
    height  int
}

func (m rootModel) Init() tea.Cmd {
    return tea.Batch(
        m.sidebar.Init(),
        m.content.Init(),
        m.status.Init(),
    )
}

func (m rootModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    var cmds []tea.Cmd

    switch msg := msg.(type) {
    case tea.KeyPressMsg:
        if msg.String() == "ctrl+c" {
            return m, tea.Quit
        }
        if msg.String() == "tab" {
            m.focused = (m.focused + 1) % 3
            return m, nil
        }
    case tea.WindowSizeMsg:
        // ALWAYS broadcast resize to ALL children
        m.width = msg.Width
        m.height = msg.Height
    }

    // Route input to focused child only
    var cmd tea.Cmd
    switch m.focused {
    case 0:
        m.sidebar, cmd = m.sidebar.Update(msg)
    case 1:
        m.content, cmd = m.content.Update(msg)
    case 2:
        m.status, cmd = m.status.Update(msg)
    }
    cmds = append(cmds, cmd)

    return m, tea.Batch(cmds...)
}

func (m rootModel) View() string {
    sidebar := m.sidebar.View()
    content := m.content.View()
    main := lipgloss.JoinHorizontal(lipgloss.Top, sidebar, content)
    return lipgloss.JoinVertical(lipgloss.Left, main, m.status.View())
}
```

Three rules for message routing:
1. **Global messages** (quit, help) — handle at the root
2. **Input messages** (keys, mouse) — route to the focused child only
3. **Broadcast messages** (`tea.WindowSizeMsg`) — forward to ALL children

For detailed architecture patterns (model tree, model stack, navigation between screens), read `references/architecture.md`.

## Lipgloss Styling

Lipgloss provides CSS-like terminal styling through method chaining:

```go
var (
    titleStyle = lipgloss.NewStyle().
        Bold(true).
        Foreground(lipgloss.Color("#FAFAFA")).
        Background(lipgloss.Color("#7D56F4")).
        Padding(0, 1)

    borderStyle = lipgloss.NewStyle().
        BorderStyle(lipgloss.RoundedBorder()).
        BorderForeground(lipgloss.Color("228")).
        Padding(1, 2)
)

// Composing layouts
header := titleStyle.Render("My App")
body := borderStyle.Width(40).Render(content)
footer := lipgloss.NewStyle().Faint(true).Render("q: quit")

view := lipgloss.JoinVertical(lipgloss.Left, header, body, footer)
```

Key layout functions:
- `lipgloss.JoinHorizontal(pos, ...)` — side by side
- `lipgloss.JoinVertical(pos, ...)` — stacked
- `lipgloss.Place(w, h, hPos, vPos, content)` — place within an area

Calculate dimensions dynamically — never hardcode:
```go
// Measure rendered content height, don't count lines manually
headerHeight := lipgloss.Height(header)
footerHeight := lipgloss.Height(footer)
contentHeight := m.height - headerHeight - footerHeight
```

## Bubbles Components

The Bubbles library provides reusable components that follow the same Model-Update-View pattern. Each component is embedded as a field in your model and needs its `Update()` called and its commands collected.

Common components: **textinput**, **textarea**, **list**, **table**, **viewport**, **spinner**, **progress**, **filepicker**, **help**, **paginator**, **timer**, **stopwatch**.

```go
type model struct {
    input   textinput.Model
    spinner spinner.Model
    list    list.Model
}

func (m model) Init() tea.Cmd {
    return tea.Batch(
        textinput.Blink,   // start cursor blinking
        m.spinner.Tick,     // start spinner animation
    )
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    var cmds []tea.Cmd
    var cmd tea.Cmd

    m.input, cmd = m.input.Update(msg)
    cmds = append(cmds, cmd)

    m.spinner, cmd = m.spinner.Update(msg)
    cmds = append(cmds, cmd)

    m.list, cmd = m.list.Update(msg)
    cmds = append(cmds, cmd)

    return m, tea.Batch(cmds...)
}
```

For component details and usage patterns, read `references/components.md`.

## Error Handling

Define an error message type and handle it consistently:

```go
type errMsg struct{ err error }
func (e errMsg) Error() string { return e.err.Error() }

// In any command
func riskyOperation() tea.Msg {
    result, err := doSomething()
    if err != nil {
        return errMsg{err}
    }
    return successMsg{result}
}

// In Update
case errMsg:
    m.err = msg.err
    return m, nil

// In View
if m.err != nil {
    return fmt.Sprintf("Error: %v\nPress r to retry, q to quit.", m.err)
}
```

After `Run()` completes, check the returned model for application errors:
```go
result, err := p.Run()
if err != nil {
    log.Fatal("framework error:", err)
}
if m := result.(model); m.err != nil {
    log.Fatal("app error:", m.err)
}
```

## Testing with teatest

```go
import "github.com/charmbracelet/x/exp/teatest"

func TestApp(t *testing.T) {
    m := initialModel()
    tm := teatest.NewTestModel(t, m, teatest.WithInitialTermSize(80, 24))

    // Wait for specific content
    teatest.WaitFor(t, tm.Output(), func(bts []byte) bool {
        return bytes.Contains(bts, []byte("Ready"))
    })

    // Send input
    tm.Send(tea.KeyPressMsg{Type: tea.KeyRunes, Runes: []rune("q")})

    // Wait for program to finish
    tm.WaitFinished(t, teatest.WithFinalTimeout(time.Second))

    // Assert on final model state
    fm := tm.FinalModel(t).(model)
    assert.Equal(t, expectedState, fm.state)
}
```

Golden file testing for View output:
```go
out, _ := io.ReadAll(tm.FinalOutput(t))
teatest.RequireEqualOutput(t, out) // compares against .golden files in testdata/
// Run with: go test ./... -update   to regenerate golden files
```

For CI, force ASCII color profile so golden files are consistent:
```go
func init() { lipgloss.SetColorProfile(termenv.Ascii) }
```

## Debugging

You cannot log to stdout — the TUI owns it. Use `tea.LogToFile`:

```go
if os.Getenv("DEBUG") != "" {
    f, err := tea.LogToFile("debug.log", "debug")
    if err != nil {
        log.Fatal(err)
    }
    defer f.Close()
}
```

Then `tail -f debug.log` in another terminal. For deeper inspection, dump all messages:

```go
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    if m.debugWriter != nil {
        spew.Fdump(m.debugWriter, msg)
    }
    // ...
}
```

## Critical Pitfalls

These are the mistakes that will waste hours of debugging time. Read `references/pitfalls.md` for the full list, but the most important ones:

1. **Never do I/O in Update()** — it blocks the entire event loop. Always use `tea.Cmd`.
2. **Always propagate `tea.WindowSizeMsg` to ALL children** — not just the focused one. Components that don't know their size will render broken layouts.
3. **Batch all Init() commands** — forgetting this causes spinners to not spin, cursors to not blink, and timers to not tick.
4. **Command results arrive in arbitrary order** — use `tea.Sequence()` when ordering matters.
5. **Never mutate model state from goroutines** — use `p.Send()` to inject messages from external code.
6. **Use `strings.Builder`** — string concatenation in View() is O(n²) and will cause visible lag with large lists.
7. **Calculate layout dynamically with `lipgloss.Height()`/`lipgloss.Width()`** — hardcoded arithmetic breaks when styling changes.

## V1 vs V2

Bubbletea v2 was released February 2025. Key differences:

| Area | v1 | v2 |
|------|----|----|
| Import | `github.com/charmbracelet/bubbletea` | `charm.land/bubbletea/v2` |
| View return | `string` | `tea.View` struct |
| Key events | `tea.KeyMsg` | `tea.KeyPressMsg` / `tea.KeyReleaseMsg` |
| Mouse events | `tea.MouseMsg` | `MouseClickMsg`, `MouseReleaseMsg`, `MouseWheelMsg`, `MouseMotionMsg` |
| Alt screen | `tea.EnterAltScreen()` cmd | `v.AltScreen = true` (declarative) |

Check the user's `go.mod` to determine which version is in use. If starting a new project, default to v1 unless the user requests v2 — v1 has more examples, docs, and community resources available. If v2 is in use, key events use `tea.KeyPressMsg` (not `tea.KeyMsg`), and `View()` returns a `tea.View` struct rather than a string.

## Reference Files

- `references/architecture.md` — Model tree, model stack, screen navigation, focus management patterns
- `references/components.md` — Detailed Bubbles component usage (textinput, list, table, viewport, spinner, progress, etc.)
- `references/pitfalls.md` — Full catalog of common mistakes and how to avoid them
