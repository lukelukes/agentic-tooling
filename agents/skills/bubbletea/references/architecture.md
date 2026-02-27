# Bubbletea Architecture Patterns

## Table of Contents
- [Model Tree (Hierarchical)](#model-tree)
- [Model Stack (Independent Screens)](#model-stack)
- [Screen Navigation](#screen-navigation)
- [Focus Management](#focus-management)
- [Custom Reusable Components](#custom-reusable-components)
- [Responsive Layout](#responsive-layout)

---

## Model Tree

The most common architecture for Bubbletea apps. A root model owns child models, routes messages down, and composes views up. Think of it as a component tree — similar to React, but with explicit message passing instead of props/callbacks.

```go
type rootModel struct {
    activeTab int
    tabs      []string
    sidebar   sidebarModel
    editor    editorModel
    statusBar statusBarModel
    width     int
    height    int
}

func (m rootModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    var cmds []tea.Cmd

    // Layer 1: Global handling
    switch msg := msg.(type) {
    case tea.KeyPressMsg:
        switch msg.String() {
        case "ctrl+c":
            return m, tea.Quit
        case "ctrl+1":
            m.activeTab = 0
            return m, nil
        case "ctrl+2":
            m.activeTab = 1
            return m, nil
        }
    case tea.WindowSizeMsg:
        // Layer 3: Broadcast to ALL children
        m.width = msg.Width
        m.height = msg.Height
        m.sidebar.SetSize(30, m.height-1)
        m.editor.SetSize(m.width-30, m.height-1)
        m.statusBar.SetSize(m.width, 1)
    }

    // Layer 2: Route input to active child
    var cmd tea.Cmd
    switch m.activeTab {
    case 0:
        m.sidebar, cmd = m.sidebar.Update(msg)
        cmds = append(cmds, cmd)
    case 1:
        m.editor, cmd = m.editor.Update(msg)
        cmds = append(cmds, cmd)
    }

    // Status bar always gets updates (timers, spinners, etc.)
    m.statusBar, cmd = m.statusBar.Update(msg)
    cmds = append(cmds, cmd)

    return m, tea.Batch(cmds...)
}

func (m rootModel) View() string {
    var active string
    switch m.activeTab {
    case 0:
        active = m.sidebar.View()
    case 1:
        active = m.editor.View()
    }
    main := lipgloss.JoinHorizontal(lipgloss.Top,
        m.sidebar.View(),
        active,
    )
    return lipgloss.JoinVertical(lipgloss.Left, main, m.statusBar.View())
}
```

Child models should expose a `SetSize(w, h int)` method rather than handling `tea.WindowSizeMsg` directly — this lets the parent control layout allocation.

### Inter-component Communication

Children communicate upward through custom message types. The parent catches these in its `Update` and acts accordingly:

```go
// Child defines a message type
type ItemSelectedMsg struct {
    ID   int
    Name string
}

// Child returns a command that produces this message
case "enter":
    return m, func() tea.Msg {
        return ItemSelectedMsg{ID: m.items[m.cursor].ID, Name: m.items[m.cursor].Name}
    }

// Parent catches it
case ItemSelectedMsg:
    m.editor.LoadItem(msg.ID)
    m.activeTab = 1 // switch to editor
```

---

## Model Stack

For wizard-style flows or apps where screens are independent and don't need to share state. Each screen is pushed/popped from a stack.

```go
type stack struct {
    screens []tea.Model
}

func (s *stack) Push(m tea.Model) tea.Cmd {
    s.screens = append(s.screens, m)
    return m.Init()
}

func (s *stack) Pop() tea.Model {
    if len(s.screens) <= 1 {
        return s.screens[0]
    }
    s.screens = s.screens[:len(s.screens)-1]
    return s.Current()
}

func (s *stack) Current() tea.Model {
    return s.screens[len(s.screens)-1]
}

// Root model using the stack
type app struct {
    stack stack
}

func (a app) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case pushScreenMsg:
        cmd := a.stack.Push(msg.model)
        return a, cmd
    case popScreenMsg:
        a.stack.Pop()
        return a, nil
    }

    // Delegate to current screen
    current := a.stack.Current()
    updated, cmd := current.Update(msg)
    a.stack.screens[len(a.stack.screens)-1] = updated
    return a, cmd
}

func (a app) View() string {
    return a.stack.Current().View()
}
```

Screen transitions use command messages:
```go
type pushScreenMsg struct{ model tea.Model }
type popScreenMsg struct{}

func pushScreen(m tea.Model) tea.Cmd {
    return func() tea.Msg { return pushScreenMsg{m} }
}
func popScreen() tea.Msg { return popScreenMsg{} }

// Usage in a child screen:
case "enter":
    return m, pushScreen(newDetailScreen(m.selectedItem))
case "esc":
    return m, popScreen
```

---

## Screen Navigation

### Enum-based (simplest)

For apps with a fixed set of screens:

```go
type screen int
const (
    menuScreen screen = iota
    gameScreen
    settingsScreen
)

type model struct {
    screen   screen
    menu     menuModel
    game     gameModel
    settings settingsModel
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case switchScreenMsg:
        m.screen = msg.to
        // Re-initialize the target screen if needed
        switch msg.to {
        case gameScreen:
            return m, m.game.Init()
        }
        return m, nil
    }

    // Route to current screen
    var cmd tea.Cmd
    switch m.screen {
    case menuScreen:
        m.menu, cmd = m.menu.Update(msg)
    case gameScreen:
        m.game, cmd = m.game.Update(msg)
    case settingsScreen:
        m.settings, cmd = m.settings.Update(msg)
    }
    return m, cmd
}

func (m model) View() string {
    switch m.screen {
    case menuScreen:
        return m.menu.View()
    case gameScreen:
        return m.game.View()
    case settingsScreen:
        return m.settings.View()
    }
    return ""
}
```

Calling `Init()` on screen transitions is important — without it, components on the new screen (spinners, timers, blinking cursors) won't start.

### Navigation Guards

Use `tea.WithFilter` to intercept messages before they reach `Update`:

```go
filter := func(m tea.Model, msg tea.Msg) tea.Msg {
    if _, ok := msg.(tea.QuitMsg); ok {
        if m.(appModel).hasUnsavedChanges {
            return confirmQuitMsg{} // redirect to confirmation
        }
    }
    return msg
}

p := tea.NewProgram(model{}, tea.WithFilter(filter))
```

---

## Focus Management

For forms and multi-component screens where Tab/Shift+Tab cycle between inputs:

```go
type formModel struct {
    inputs  []textinput.Model
    focused int
}

func (m *formModel) focusNext() tea.Cmd {
    m.inputs[m.focused].Blur()
    m.focused = (m.focused + 1) % len(m.inputs)
    return m.inputs[m.focused].Focus()
}

func (m *formModel) focusPrev() tea.Cmd {
    m.inputs[m.focused].Blur()
    m.focused = (m.focused - 1 + len(m.inputs)) % len(m.inputs)
    return m.inputs[m.focused].Focus()
}

func (m formModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyPressMsg:
        switch msg.String() {
        case "tab", "down":
            return m, m.focusNext()
        case "shift+tab", "up":
            return m, m.focusPrev()
        case "enter":
            if m.focused == len(m.inputs)-1 {
                return m, m.submit()
            }
            return m, m.focusNext()
        }
    }

    // Only update the focused input
    var cmd tea.Cmd
    m.inputs[m.focused], cmd = m.inputs[m.focused].Update(msg)
    return m, cmd
}
```

---

## Custom Reusable Components

Build components that implement `tea.Model` and communicate via custom message types:

```go
// ---- Public API ----

type Model struct {
    items   []Item
    cursor  int
    focused bool
    width   int
    height  int
}

type Item struct {
    Title       string
    Description string
}

// Messages this component can produce
type SelectedMsg struct{ Item Item }

func New(items []Item) Model {
    return Model{items: items}
}

func (m *Model) SetSize(w, h int) { m.width = w; m.height = h }
func (m *Model) Focus()           { m.focused = true }
func (m *Model) Blur()            { m.focused = false }
func (m Model) Focused() bool     { return m.focused }
func (m Model) Selected() Item    { return m.items[m.cursor] }

// ---- tea.Model implementation ----

func (m Model) Init() tea.Cmd { return nil }

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
    if !m.focused {
        return m, nil
    }
    switch msg := msg.(type) {
    case tea.KeyPressMsg:
        switch msg.String() {
        case "up", "k":
            if m.cursor > 0 {
                m.cursor--
            }
        case "down", "j":
            if m.cursor < len(m.items)-1 {
                m.cursor++
            }
        case "enter":
            return m, func() tea.Msg {
                return SelectedMsg{Item: m.items[m.cursor]}
            }
        }
    }
    return m, nil
}

func (m Model) View() string {
    var b strings.Builder
    for i, item := range m.items {
        cursor := "  "
        if i == m.cursor {
            cursor = "> "
        }
        fmt.Fprintf(&b, "%s%s\n", cursor, item.Title)
    }
    return b.String()
}
```

The component returns its own concrete type from `Update` (not `tea.Model`) — this avoids type assertions in the parent. The parent calls it like:

```go
m.picker, cmd = m.picker.Update(msg)
```

---

## Responsive Layout

Handle terminal resizing gracefully. `tea.WindowSizeMsg` arrives once at startup and on every resize.

```go
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.WindowSizeMsg:
        m.width = msg.Width
        m.height = msg.Height

        // Responsive breakpoints
        if m.width < 80 {
            m.compact = true
            m.list.SetSize(m.width, m.height-2)
        } else {
            m.compact = false
            sidebarWidth := 30
            m.sidebar.SetSize(sidebarWidth, m.height-1)
            m.content.SetSize(m.width-sidebarWidth, m.height-1)
        }
        m.statusBar.SetSize(m.width, 1)
    }
    return m, nil
}

func (m model) View() string {
    if m.compact {
        // Stack vertically in narrow terminals
        return lipgloss.JoinVertical(lipgloss.Left,
            m.list.View(),
            m.statusBar.View(),
        )
    }
    // Side by side in wide terminals
    main := lipgloss.JoinHorizontal(lipgloss.Top,
        m.sidebar.View(),
        m.content.View(),
    )
    return lipgloss.JoinVertical(lipgloss.Left, main, m.statusBar.View())
}
```

Use `lipgloss.Height()` and `lipgloss.Width()` to measure rendered strings rather than counting lines or characters manually. This accounts for borders, padding, and multi-byte characters correctly.

```go
header := renderHeader()
footer := renderFooter()
availableHeight := m.height - lipgloss.Height(header) - lipgloss.Height(footer)
m.viewport.Height = availableHeight
```
