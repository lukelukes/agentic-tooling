# Server stack for the map view

Research for wayfinder ticket `map-view/02-server-stack`. Date: 2026-10-21.

## Question

Which stack fits a contained, locally run live server for the **map view**? The
server is part of a companion skill in this repo. It lives in its own folder and
may bring its own toolchain. It must:

- watch plain markdown files across several registered repos;
- push changes to the browser live;
- typeset plain markdown well (GFM, maybe mermaid);
- lay out a design tree and a round timeline;
- accept one write from the browser: an answer to a round, written back to a
  markdown file.

## Short answer

Use **Deno**, with server-sent events (SSE) for push and a plain `POST` for the
answer write. Do markdown and layout with small npm libraries: `markdown-it`
for GFM, `d3-hierarchy` for the tree, and `mermaid` loaded only when a page has
a mermaid fence. Pin them in `deno.json` and `deno.lock`, and use
`"vendor": true` so the dependency code stays in the skill folder. You need no
`package.json`, no `node_modules` and no build step.

The runner-up is **Python stdlib with vanilla JS and vendored browser
libraries**. It matches the `sync.py` ethos exactly. The cost is polling
instead of a native file watcher, a hand-rolled SSE loop, and all markdown
work moving into the browser. Choose it if "no new runtime" weighs more than
the points below.

## Facts about this machine

Checked on 2026-10-21 with `--version`, `which` and `pacman -Q`:

| Runtime | On `PATH` | From | Arch repo version |
|---|---|---|---|
| Python | 3.14.7, `/usr/bin/python3` | pacman (`core`) | 3.14.8 |
| Deno | 2.9.5, `/usr/bin/deno` | pacman (`extra`) | 2.9.7 |
| Node | v25.6.1, mise install | mise (pacman `nodejs` 26.7.0 also installed, shadowed) | 26.12.0 |
| Bun | 1.3.5 via the mise shim; mise also holds 1.3.10 | mise | 1.4.3 |
| npm / pnpm / uv | 11.9.0 / 12.3.4 / 0.5.11 | — | — |

Repo-version numbers and installed sizes come from the Arch package JSON API
(`https://archlinux.org/packages/search/json/?name=<pkg>`): bun 1.4.3, 70.2 MB
installed; deno 2.9.7, 111.9 MB; nodejs 26.12.0, 67.2 MB, plus npm 9.9 MB
(npm is only an optional dependency of `nodejs`, see
<https://archlinux.org/packages/extra/x86_64/nodejs/>); python 3.14.8,
77.4 MB.

So all four runtimes are already installed. All four are in the official Arch
repos, so the install story is `pacman -S` for each. Bun's own docs list only
curl, npm, Homebrew, Docker and zip downloads, not the Arch package
(<https://bun.com/docs/installation>).

### Startup time (measured)

This is the time from spawning the process to the first successful HTTP
response, for a hello-world server, averaged over 10 runs on this machine. The
script is in the session scratchpad. It used `http.server` / `node:http` /
`Bun.serve` / `Deno.serve`.

| Runtime | ms |
|---|---|
| Deno 2.9.5 | 23–44 |
| Bun 1.3.10 (direct binary) | 32 |
| Python 3.14.7 | 44–49 |
| Node v25.6.1 | 49–52 |
| Bun 1.3.5 (through the mise shim) | 110–122 |

All of them start in well under 100 ms. Startup does not separate the
candidates. The only outlier is the mise shim, which adds about 80 ms. It also
resolved a different Bun version (1.3.5) from the newest one mise holds
(1.3.10). A skill that shells out to `bun` through mise inherits that drift.

## Candidates

### 1. Deno (recommended)

- **Toolchain:** one binary from `extra`, already installed at `/usr/bin/deno`.
  TypeScript runs directly.
- **Watch:** `Deno.watchFs(paths)` takes several paths at once. `recursive`
  defaults to `true`, and it needs only `--allow-read`
  (<https://docs.deno.com/api/deno/~/Deno.watchFs>). Several registered repos
  map onto a single watcher.
- **Push:** `Deno.serve` returns web-standard `Response`s, and "Response bodies
  can also be streams". That gives SSE without a library. There is also
  `Deno.upgradeWebSocket`. The docs warn that you must handle `cancel` when the
  client hangs up, or messages queue up without limit
  (<https://docs.deno.com/runtime/fundamentals/http_server/>).
- **The one write:** Deno is "sandboxed by default", and permissions "can be
  scoped to specific resources", for example `--allow-read=./data`
  (<https://docs.deno.com/runtime/fundamentals/security/>). Scope
  `--allow-write` to the registered repos' map folders and the process cannot
  write anywhere else. This enforces the glossary rule that the map view's
  only write is an answer. No other candidate gives this for free.
- **Dependencies:** npm packages work through `npm:` specifiers. Deno keeps a
  lockfile with integrity hashes, and `"vendor": true` caches dependencies in a
  local `vendor` directory instead of the global `DENO_DIR`. Without a
  `package.json`, Deno creates no `node_modules`
  (<https://docs.deno.com/runtime/packages/>).
- **Containment:** `deno.json`, `deno.lock`, `vendor/` and the source all sit
  in the skill folder. `deno compile` can also produce a "standalone
  executable" (<https://docs.deno.com/runtime/reference/cli/compile/>), but
  this is not needed.
- **Cost:** the largest binary (111.9 MB installed). Write scopes are fixed
  when the process starts, so registering a new repo means a restart. A wrapper
  can read the registry and pass the `--allow-*` paths.

### 2. Python stdlib + vanilla JS (runner-up)

- **Toolchain:** none beyond what `sync.py` already needs.
- **Server:** `ThreadingHTTPServer` (3.7+) handles browsers that pre-open
  sockets, "on which HTTPServer would wait indefinitely". Python warns that
  `http.server` "is not recommended for production. It only implements basic
  security checks" (<https://docs.python.org/3/library/http.server.html>).
  That is acceptable on loopback.
- **Push:** you write SSE by hand to `wfile`. The default `HTTP/1.0` protocol
  allows an unbounded body. Under `HTTP/1.1` the docs require an accurate
  `Content-Length` (same page), so stay on 1.0 for the event stream.
- **Watch:** the stdlib has no file-change notification API. You poll mtimes
  instead. That is cheap for a few hundred markdown files at about 500 ms. The
  native option is `watchfiles`, which is built on the Rust `notify` crate
  (<https://github.com/samuelcolvin/watchfiles>) and is in `extra` as
  `python-watchfiles`. It breaks the no-deps rule.
- **Markdown:** no stdlib renderer. `markdown-it-py` follows CommonMark but
  "Tables are disabled by default"
  (<https://github.com/executablebooks/markdown-it-py>). In practice markdown
  rendering and tree layout move to the browser, using vendored ESM files of
  the same JS libraries as candidate 1.
- **Containment:** excellent. Only `.py` files and checked-in `.js` files.
- **Cost:** you hand-roll the plumbing (SSE framing, polling, routing), and
  the browser parses markdown it cannot verify against the server's view.

### 3. Bun

- **Toolchain:** in `extra` (1.4.3, 70.2 MB). Locally it is only installed
  through mise, and the shim drifts, as measured above.
- **Watch:** Bun implements `node:fs` `fs.watch`. Use `recursive: true` for
  subdirectories (<https://bun.com/docs/guides/read-file/watch>).
- **Push:** `Bun.serve` has built-in WebSockets with server-wide handlers and
  topic pub/sub. `server.publish(topic, data)` reaches every subscriber
  (<https://bun.com/docs/runtime/http/websockets>).
- **Frontend:** `Bun.serve` routes can import `.html` files. Bun "automatically
  bundles the `<script>` and `<link>` tags", and `development: true` turns on
  HMR (<https://bun.com/docs/bundler/fullstack>). This is the smoothest path
  if the UI grows into a real bundled app.
- **Containment:** `package.json` + `bun.lock` + `node_modules` in the skill
  folder. `sync.py` symlinks the whole skill directory into `~/.claude/skills`,
  `~/.agents/skills` and `~/.cursor/skills` (`sync.py`, `SKILL_ROOTS`), so a
  `node_modules` tree would show up in all three. It needs a `.gitignore`
  entry and an install step on fresh clones.
- **Cost:** no permission sandbox, and it adds a runtime that is not otherwise
  pinned system-wide.

### 4. Node + small framework (or Vite dev server)

- **Watch:** `fs.watch` gained recursive support on Linux in v19.1.0. On Linux
  it uses `inotify(7)`
  (<https://github.com/nodejs/node/blob/main/doc/api/fs.md>, history and
  Availability of `fs.watch`).
- **Push:** Node has a global `WebSocket`, but it is "a browser-compatible
  implementation", meaning a client
  (<https://github.com/nodejs/node/blob/main/doc/api/globals.md>). A WebSocket
  server needs `ws` (8.22.0, 0 deps, npm registry). SSE needs nothing.
- **TypeScript:** type stripping has been stable since v25.2.0 / v24.12.0
  (<https://github.com/nodejs/node/blob/main/doc/api/typescript.md>).
- **Vite:** the dev server can push custom events with `server.ws.send`, which
  the client receives with `import.meta.hot.on`. Middleware goes in
  `configureServer` (<https://vite.dev/guide/api-plugin>). Watching markdown
  that lives in *other* repos, outside Vite's root, goes against that grain.
  Vite's HMR is for the app's own source.
- **Astro:** 52 runtime dependencies (npm registry, `astro@7.4.2`). It is a
  site generator, and an answer write plus multi-repo watching fit it badly.
  Ruled out.
- **Containment / cost:** the same `node_modules` issue as Bun, and the Node on
  `PATH` is a mise install that shadows pacman's. Node offers nothing here that
  Deno lacks, and it has more moving parts.

## Push mechanism: SSE over WebSocket

The browser sends one kind of message (an answer), and a plain `POST` covers
it. Everything else flows from server to browser, which is exactly what SSE
does. `EventSource` reconnects automatically, and the server can tune the
delay with `retry:`
(<https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events>).

One caveat from the same page: over HTTP/1.1, browsers cap SSE at 6 open
connections per browser and domain. Give each tab one `EventSource` that
carries events for every registered map, not one stream per map.

## Rendering libraries (any JS candidate, or the browser)

| Need | Pick | Evidence |
|---|---|---|
| GFM markdown | `markdown-it` 15.0.3 | "Safe by default" (README). `html: false` in the default preset. Tables and strikethrough are core rules (`src/parser_block.ts`, `src/parser_inline.ts`, <https://github.com/markdown-it/markdown-it>). Task lists need a plugin (`markdown-it-task-lists`). |
| Alternative | `marked` 18.1.1, 0 deps | `gfm` defaults to `true`. It does not sanitize: the docs point to DOMPurify (<https://marked.js.org/using_advanced>). |
| Full GFM incl. footnotes | `remark-gfm` 4.0.1 | "autolink literals, footnotes, strikethrough, tables, tasklists" (<https://github.com/remarkjs/remark-gfm>). Pulls in the unified/micromark tree. |
| Mermaid | `mermaid` 12.2.0 | ESM build. `startOnLoad: false` plus `mermaid.run({nodes})` for on-demand render. `securityLevel` defaults to `strict` (<https://mermaid.js.org/config/usage.html>). The npm package is 122 MB unpacked, so lazy-load it only when a ```` ```mermaid ```` fence exists. |
| Design tree layout | `d3-hierarchy` 3.1.2, 0 deps, 0.14 MB | Reingold–Tilford "tidy" tree in linear time. `nodeSize` and `separation` control spacing (<https://d3js.org/d3-hierarchy/tree>). |
| If the tree turns out to be a DAG | `@dagrejs/dagre` 3.1.1 (1.41 MB) or `elkjs` 0.12.0 (8 MB, EPL/GPL) | npm registry metadata. |
| Round timeline | plain HTML/CSS | A vertical list of rounds needs no library. |

Package versions, sizes and dependency counts come from
`https://registry.npmjs.org/<pkg>/latest` on 2026-10-21.

## Comparison

| | Deno | Python stdlib | Bun | Node / Vite |
|---|---|---|---|---|
| Install on Arch | in `extra`, installed | in `core`, installed | in `extra`; locally mise only | in `extra`; locally mise shadows it |
| Native recursive watch | yes, multi-path | no (poll) | yes | yes (v19.1+) |
| SSE / WS built in | both | SSE by hand | both + pub/sub | SSE; WS needs `ws` |
| Markdown on server | npm libs | needs deps, so browser | npm libs | npm libs |
| Folder stays self-contained | `deno.json` + lock + `vendor/` | trivially | `node_modules` | `node_modules` |
| Restricts the one write | `--allow-write=<paths>` | no | no | no |
| Startup | ~23–44 ms | ~45 ms | ~32 ms direct | ~50 ms |

## Open points this surfaces

- **Registry and permissions:** if the server enforces write scope with
  `--allow-write`, the registry of maps must be read before launch. Adding a
  map at runtime then means a restart or a broader scope.
- **Where markdown is parsed:** on the server (one parse, a structured design
  tree over SSE) or in the browser (dumb server). This decides how the server
  learns the design-tree shape from plain markdown files.
- **Port and lifecycle:** how the companion skill starts, finds and stops the
  server (fixed port, port file, one server for all registered repos).
