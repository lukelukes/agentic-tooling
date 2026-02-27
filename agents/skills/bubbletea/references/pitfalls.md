# Common Bubbletea Pitfalls

These are the mistakes that cost real debugging time. They're ordered roughly by how often they bite people.

---

## 1. Blocking the Event Loop

The event loop processes messages sequentially — `Update()` then `View()`, over and over. If either blocks, the entire UI freezes.

```go
// WRONG: blocks the event loop, UI freezes during fetch
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    case "r":
        data := fetchFromAPI() // blocks for seconds!
        m.data = data
        return m, nil
}

// RIGHT: offload to a command
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    case "r":
        m.loading = true
        return m, fetchFromAPI // runs in a goroutine
}

func fetchFromAPI() tea.Msg {
    resp, err := http.Get("https://api.example.com/data")
    if err != nil {
        return errMsg{err}
    }
    defer resp.Body.Close()
    var data Data
    json.NewDecoder(resp.Body).Decode(&data)
    return dataMsg{data}
}
```

This applies equally to `View()` — keep rendering fast. Pre-compute expensive string operations in `Update` and cache the results.

---

## 2. Forgetting to Propagate WindowSizeMsg

`tea.WindowSizeMsg` arrives once at startup and on every terminal resize. Child components that don't receive it will render at zero size or with stale dimensions.

```go
// WRONG: only sends resize to focused child
case tea.WindowSizeMsg:
    m.width = msg.Width
    m.height = msg.Height
    switch m.focused {
    case 0:
        m.sidebar.SetSize(30, m.height)
    case 1:
        m.content.SetSize(m.width-30, m.height) // sidebar never gets resized!
    }

// RIGHT: always resize ALL children
case tea.WindowSizeMsg:
    m.width = msg.Width
    m.height = msg.Height
    m.sidebar.SetSize(30, m.height)
    m.content.SetSize(m.width-30, m.height)
    m.status.SetSize(m.width, 1)
```

---

## 3. Forgetting to Batch Init Commands

Each Bubbles component may need an initialization command — spinners need `Tick`, text inputs need `Blink`, timers need `Init()`. If you forget to batch them, those components appear broken.

```go
// WRONG: only spinner works
func (m model) Init() tea.Cmd {
    return m.spinner.Tick // text input cursor won't blink!
}

// RIGHT: all components get their init commands
func (m model) Init() tea.Cmd {
    return tea.Batch(
        textinput.Blink,
        m.spinner.Tick,
        m.timer.Init(),
    )
}
```

Same applies when switching screens — call `Init()` on the new screen's model.

---

## 4. Message Ordering Assumptions

User input (keypresses, mouse) arrives in order because it comes from a single goroutine. But command results are concurrent — they can arrive in any order.

```go
// These may complete in any order
return m, tea.Batch(
    fetchUsers,   // might finish second
    fetchPosts,   // might finish first
)

// If order matters, use Sequence
return m, tea.Sequence(
    validateData,
    saveData,     // guaranteed to run after validate
)
```

Design your `Update` to handle messages arriving in any order. Don't assume `dataMsg` arrives before `statusMsg` just because you sent the commands in that order.

---

## 5. Mutating State from Goroutines

The model should only be modified inside `Update()`. Modifying it from goroutines creates race conditions that manifest as corrupted UI, panics, or subtle data bugs.

```go
// WRONG: race condition
go func() {
    data := fetchData()
    m.data = data // RACE: model is being read by View() concurrently
}()

// RIGHT: send a message through the event loop
go func() {
    data := fetchData()
    p.Send(dataMsg{data}) // safe: goes through Update()
}()

// BEST: use a tea.Cmd instead of raw goroutines
func fetchData() tea.Msg {
    data := doFetch()
    return dataMsg{data}
}
return m, fetchData
```

---

## 6. Logging to Stdout

The TUI owns stdout. Anything you print there corrupts the display.

```go
// WRONG: corrupts the TUI
fmt.Println("debug:", value)
log.Println("something happened")

// RIGHT: log to a file
f, err := tea.LogToFile("debug.log", "debug")
if err != nil {
    log.Fatal(err)
}
defer f.Close()

// Then use log.Print() normally — it goes to the file
log.Printf("value: %v", value)
// Monitor in another terminal: tail -f debug.log
```

---

## 7. Hardcoded Layout Dimensions

Counting border/padding pixels by hand is fragile. When you change a style (add a border, increase padding), the arithmetic breaks.

```go
// WRONG: breaks when header styling changes
m.viewport.Height = m.height - 2 // assumes header is 2 lines

// RIGHT: measure the rendered content
header := m.renderHeader()
footer := m.renderFooter()
m.viewport.Height = m.height - lipgloss.Height(header) - lipgloss.Height(footer)
```

---

## 8. String Concatenation in View()

`View()` is called on every update. String concatenation with `+` or `+=` is O(n²) for n items.

```go
// WRONG: O(n²), causes visible lag with >100 items
func (m model) View() string {
    s := ""
    for _, item := range m.items {
        s += renderItem(item) + "\n"
    }
    return s
}

// RIGHT: O(n) with strings.Builder
func (m model) View() string {
    var b strings.Builder
    b.Grow(len(m.items) * 80) // optional: pre-allocate
    for _, item := range m.items {
        b.WriteString(renderItem(item))
        b.WriteByte('\n')
    }
    return b.String()
}
```

For truly large lists (1000+ items), also limit rendering to only visible items:
```go
start := m.offset
end := min(m.offset+m.visibleRows, len(m.items))
for i := start; i < end; i++ {
    b.WriteString(m.renderRow(i))
    b.WriteByte('\n')
}
```

---

## 9. Panics in Commands Corrupt the Terminal

Bubbletea recovers from panics in the main event loop, but not in commands (which run in separate goroutines). A panic in a command leaves the terminal in raw mode — no cursor, no echo.

Recovery: type `reset` (even if you can't see what you're typing) and press Enter.

Prevention: add panic recovery in commands that call external code:

```go
func riskyCommand() tea.Msg {
    defer func() {
        if r := recover(); r != nil {
            // recovered, but can't easily send an error message
            // at minimum, log it
            log.Printf("panic in command: %v", r)
        }
    }()
    return doRiskyThing()
}
```

---

## 10. Not Calling Update on Child Components

If you embed a Bubbles component but don't call its `Update`, it's completely inert — no cursor blinking, no key handling, no animations.

```go
// WRONG: spinner never updates, appears frozen
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    // forgot to update m.spinner
    return m, nil
}

// RIGHT: always update embedded components
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    var cmds []tea.Cmd
    var cmd tea.Cmd

    m.spinner, cmd = m.spinner.Update(msg)
    cmds = append(cmds, cmd)

    // ... handle other messages ...

    return m, tea.Batch(cmds...)
}
```

---

## 11. Value Receiver Confusion

Bubbletea examples use value receivers (following Elm's functional model). This confuses Go developers who expect mutations to persist without returning the modified model.

```go
// Value receiver: mutations only affect the local copy
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    m.cursor++ // this modifies the local copy
    return m, nil // must return the modified copy!
}
```

If you use pointer receivers, be careful not to modify state from goroutines (see pitfall #5). Value receivers are the safer default.

---

## 12. Live Reload Tooling

Tools like `air` don't work with TUI programs because they don't connect stdin as a TTY. Use `watchexec` instead:

```bash
watchexec -r -e go -- go run .
```

---

## 13. No Timeout on HTTP Commands

Bubbletea has no built-in timeout for commands. An HTTP request that hangs forever creates a goroutine leak and the user's action appears to do nothing.

```go
// WRONG: no timeout, may hang forever
func fetchData() tea.Msg {
    resp, err := http.Get(url)
    // ...
}

// RIGHT: always set a timeout
func fetchData() tea.Msg {
    client := &http.Client{Timeout: 10 * time.Second}
    resp, err := client.Get(url)
    if err != nil {
        return errMsg{err} // timeout produces a clear error
    }
    // ...
}
```
