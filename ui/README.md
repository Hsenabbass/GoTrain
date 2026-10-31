# GoTrain UI prototype

Local-only, dependency-free model-building UI. Requires Node.js 18 or later.

```powershell
cd C:\Users\ahmad\GoTrain\ui
node server.mjs
```

Open http://localhost:5173. Stop with Ctrl+C. No install, account, publishing, external requests, or backend is required.

## Task to model

The neutral workspace uses a bottom input for submitting a task, not a conversation. Starter options fill editable task templates. Add a dataset reference, describe the required outcome, select a time budget, and choose **Build model**. Enter submits; Shift+Enter inserts a line break.

The roughly 24-second simulation shows preparation, training, evaluation, and packaging. Completion displays a model-result card with summary export, output preview, and experiment history. There are no assistant replies, thinking delays, pets, or companion settings. Header and view navigation stay visible while scrolling.

**All model results are illustrative.** No actual model is trained or returned. Exports are demo JSON summaries without weights. Dataset selection records a filename only; local images use browser object URLs. Files are never uploaded. Projects persist in browser localStorage; job progress and game state last for the current page session. Reloading ends the UI simulation. This work does not advance any ML milestone.

## Optional keyboard game

**Rover Run** is suggested while a task executes and is available in the sidebar. It opens only when selected. Drive around falling rocks, collect gold energy cells (+15 points), and survive as speed increases. Arrow keys or WASD move in four directions; Space starts/pauses, R restarts, and Escape closes. Survival also earns points. The game has a current-session best score.

Keyboard controls apply only while the game canvas has focus. Losing focus, switching browser tabs, closing the game, or switching project views pauses it. Closing or pausing the game does not affect model execution. Task completion does not dismiss the game.

## Organization

- `src/app.js`: project state, task submission, execution simulation, and model delivery.
- `src/pages/workspace.js`: experiment history and prediction views.
- `src/components/scene.js`: original SVG aerial illustration.
- `src/components/rover-game.js`: keyboard arcade game, canvas rendering, and game lifecycle.
- `src/mocks/projects.js`: illustrative projects and experiment records.
- `src/styles/main.css`: neutral visual system and responsive layout.
- `server.mjs`: loopback-only static server.

Run `npm run check` if npm is available, or `node --check` against the JavaScript files.
