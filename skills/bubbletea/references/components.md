# Bubbles Component Reference

The Bubbles library (`github.com/charmbracelet/bubbles`) provides reusable TUI components that follow the same Model-Update-View pattern as Bubbletea itself. Each component is embedded in your model, needs its `Update()` called, and its commands collected.

## Table of Contents
- [Text Input](#text-input)
- [Text Area](#text-area)
- [List](#list)
- [Table](#table)
- [Viewport](#viewport)
- [Spinner](#spinner)
- [Progress](#progress)
- [File Picker](#file-picker)
- [Help](#help)
- [Timer and Stopwatch](#timer-and-stopwatch)
- [Paginator](#paginator)

---

## Text Input

Single-line text entry with cursor, placeholder, validation, and echo modes (normal, password, none).

```go
import "github.com/charmbracelet/bubbles/textinput"

ti := textinput.New()
ti.Placeholder = "Enter your name"
ti.CharLimit = 50
ti.Width = 30
ti.Focus() // Must call Focus() for it to accept input

// Password mode
ti.EchoMode = textinput.EchoPassword
ti.EchoCharacter = '•'

// Validation
ti.Validate = func(s string) error {
    if len(s) > 0 && !unicode.IsLetter(rune(s[len(s)-1])) {
        return fmt.Errorf("letters only")
    }
    return nil
}

// Init must include Blink for the cursor to work
func (m model) Init() tea.Cmd {
    return textinput.Blink
}

// Get the value
value := ti.Value()
```

## Text Area

Multi-line text editing with vertical scrolling.

```go
import "github.com/charmbracelet/bubbles/textarea"

ta := textarea.New()
ta.Placeholder = "Type your message..."
ta.SetWidth(60)
ta.SetHeight(10)
ta.Focus()

// Set initial content
ta.SetValue("Hello\nWorld")

// Get content
content := ta.Value()
```

## List

Batteries-included item browser with fuzzy filtering, pagination, status messages, and keyboard navigation. This is one of the most feature-rich Bubbles components.

```go
import "github.com/charmbracelet/bubbles/list"

// Items must implement list.Item interface
type item struct {
    title string
    desc  string
}
func (i item) Title() string       { return i.title }
func (i item) Description() string { return i.desc }
func (i item) FilterValue() string { return i.title }

// Create the list
items := []list.Item{
    item{title: "Raspberry Pi", desc: "A tiny computer"},
    item{title: "Arduino", desc: "A microcontroller"},
}
l := list.New(items, list.NewDefaultDelegate(), 40, 20)
l.Title = "My List"

// Customize keybindings
l.KeyMap.Quit = key.NewBinding(key.WithKeys("q"))

// In Update, the list handles its own navigation, filtering, etc.
m.list, cmd = m.list.Update(msg)

// Get selected item
if i, ok := m.list.SelectedItem().(item); ok {
    selected = i
}

// Programmatically set items
m.list.SetItems(newItems)

// Status message (auto-dismisses)
cmd = m.list.NewStatusMessage("Item deleted!")
```

## Table

Tabular data with column headers, row navigation, and styling.

```go
import "github.com/charmbracelet/bubbles/table"

columns := []table.Column{
    {Title: "Name", Width: 20},
    {Title: "Age", Width: 5},
    {Title: "City", Width: 15},
}

rows := []table.Row{
    {"Alice", "30", "Portland"},
    {"Bob", "25", "Seattle"},
    {"Charlie", "35", "Austin"},
}

t := table.New(
    table.WithColumns(columns),
    table.WithRows(rows),
    table.WithFocused(true),
    table.WithHeight(10),
)

// Style the table
s := table.DefaultStyles()
s.Header = s.Header.
    BorderStyle(lipgloss.NormalBorder()).
    BorderForeground(lipgloss.Color("240")).
    Bold(true)
s.Selected = s.Selected.
    Foreground(lipgloss.Color("229")).
    Background(lipgloss.Color("57"))
t.SetStyles(s)

// Get selected row
row := t.SelectedRow() // returns table.Row ([]string)
```

## Viewport

Vertically scrollable content area. Essential for displaying content taller than the terminal.

```go
import "github.com/charmbracelet/bubbles/viewport"

// Usually initialized after receiving WindowSizeMsg (lazy init)
type model struct {
    viewport viewport.Model
    ready    bool
    content  string
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.WindowSizeMsg:
        headerHeight := 3
        footerHeight := 1
        if !m.ready {
            m.viewport = viewport.New(msg.Width, msg.Height-headerHeight-footerHeight)
            m.viewport.YPosition = headerHeight
            m.viewport.SetContent(m.content)
            m.ready = true
        } else {
            m.viewport.Width = msg.Width
            m.viewport.Height = msg.Height - headerHeight - footerHeight
        }
    }

    var cmd tea.Cmd
    m.viewport, cmd = m.viewport.Update(msg)
    return m, cmd
}

// Scroll info for a footer
percent := m.viewport.ScrollPercent()
footer := fmt.Sprintf(" %3.f%% ", percent*100)
```

The viewport handles Page Up/Down, Home/End, arrow keys, and mouse wheel automatically.

## Spinner

Animated loading indicators with several built-in styles.

```go
import "github.com/charmbracelet/bubbles/spinner"

s := spinner.New()
s.Spinner = spinner.Dot      // or: Line, MiniDot, Jump, Pulse, Points, Globe, Moon, Monkey, Meter, Hamburger
s.Style = lipgloss.NewStyle().Foreground(lipgloss.Color("205"))

// Init must include Tick
func (m model) Init() tea.Cmd {
    return m.spinner.Tick
}

// View
fmt.Sprintf("%s Loading...", m.spinner.View())
```

## Progress

Customizable progress bar with optional animation.

```go
import "github.com/charmbracelet/bubbles/progress"

p := progress.New(
    progress.WithDefaultGradient(),    // or WithGradient("#FF0000", "#00FF00")
    progress.WithWidth(40),
    progress.WithoutPercentage(),      // hide percentage text
)

// Set progress (0.0 to 1.0)
cmd := p.SetPercent(0.75)

// Or increment
cmd := p.IncrPercent(0.1)

// In Update, handle the animation frame messages
case progress.FrameMsg:
    progressModel, cmd := m.progress.Update(msg)
    m.progress = progressModel.(progress.Model)
    return m, cmd
```

## File Picker

Filesystem navigation with extension filtering.

```go
import "github.com/charmbracelet/bubbles/filepicker"

fp := filepicker.New()
fp.AllowedTypes = []string{".go", ".mod", ".sum"}
fp.CurrentDirectory, _ = os.Getwd()

// Init
func (m model) Init() tea.Cmd {
    return m.filepicker.Init()
}

// In Update
case tea.KeyPressMsg:
    // filepicker handles navigation internally

m.filepicker, cmd = m.filepicker.Update(msg)

// Check if a file was selected
if didSelect, path := m.filepicker.DidSelectFile(msg); didSelect {
    m.selectedFile = path
}

// Check if selection was disabled (e.g., directory with no matching files)
if didSelect, path := m.filepicker.DidSelectDisabledFile(msg); didSelect {
    m.err = fmt.Errorf("%s is not a valid file", path)
}
```

## Help

Auto-generated keybinding help display.

```go
import (
    "github.com/charmbracelet/bubbles/help"
    "github.com/charmbracelet/bubbles/key"
)

// Define your keybindings
type keyMap struct {
    Up    key.Binding
    Down  key.Binding
    Quit  key.Binding
}

func (k keyMap) ShortHelp() []key.Binding {
    return []key.Binding{k.Up, k.Down, k.Quit}
}

func (k keyMap) FullHelp() [][]key.Binding {
    return [][]key.Binding{
        {k.Up, k.Down},
        {k.Quit},
    }
}

var keys = keyMap{
    Up:   key.NewBinding(key.WithKeys("up", "k"), key.WithHelp("↑/k", "up")),
    Down: key.NewBinding(key.WithKeys("down", "j"), key.WithHelp("↓/j", "down")),
    Quit: key.NewBinding(key.WithKeys("q", "ctrl+c"), key.WithHelp("q", "quit")),
}

h := help.New()

// In View
helpView := h.View(keys) // renders: ↑/k up • ↓/j down • q quit

// Toggle full help
case "?":
    h.ShowAll = !h.ShowAll
```

## Timer and Stopwatch

```go
import "github.com/charmbracelet/bubbles/timer"
import "github.com/charmbracelet/bubbles/stopwatch"

// Countdown timer
t := timer.NewWithInterval(5*time.Minute, time.Second)

func (m model) Init() tea.Cmd {
    return m.timer.Init()
}

case timer.TickMsg:
    var cmd tea.Cmd
    m.timer, cmd = m.timer.Update(msg)
    return m, cmd
case timer.TimeoutMsg:
    m.timerDone = true

// Stopwatch (counts up)
sw := stopwatch.NewWithInterval(time.Second)

func (m model) Init() tea.Cmd {
    return m.stopwatch.Init()
}
```

## Paginator

Page navigation for splitting content across pages.

```go
import "github.com/charmbracelet/bubbles/paginator"

p := paginator.New()
p.Type = paginator.Dots  // or paginator.Arabic ("1/3")
p.PerPage = 10
p.SetTotalPages(len(items))

// Get items for current page
start, end := p.GetSliceBounds(len(items))
pageItems := items[start:end]

// In View
paginatorView := p.View() // renders: • ○ ○
```

---

## Pattern: Initializing Multiple Components

When your model uses several Bubbles components, batch all their init commands:

```go
func (m model) Init() tea.Cmd {
    return tea.Batch(
        textinput.Blink,      // text input cursor
        m.spinner.Tick,        // spinner animation
        m.timer.Init(),        // timer ticks
        m.list.StartSpinner(), // list's built-in spinner
    )
}
```

Forgetting any of these causes that component to appear frozen.

## Pattern: Updating Multiple Components

Collect commands from all active components:

```go
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    var cmds []tea.Cmd
    var cmd tea.Cmd

    // Update each component
    m.input, cmd = m.input.Update(msg)
    cmds = append(cmds, cmd)

    m.list, cmd = m.list.Update(msg)
    cmds = append(cmds, cmd)

    m.spinner, cmd = m.spinner.Update(msg)
    cmds = append(cmds, cmd)

    return m, tea.Batch(cmds...)
}
```

If components conflict on keybindings (e.g., both a list and a text input want arrow keys), only update the focused one:

```go
if m.inputFocused {
    m.input, cmd = m.input.Update(msg)
} else {
    m.list, cmd = m.list.Update(msg)
}
```
