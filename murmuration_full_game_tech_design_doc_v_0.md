# Murmuration — Full Game & Tech Design Doc (v0.1)

**High concept:** An “influence-not-control” evolution sandbox where players guide migratory micro-bird flocks using environmental signals. Agents learn across seasons via lightweight ML. Challenge comes from level-based *Migration Contracts* with hard constraints (time, losses, cohesion, diversity, budget).

---

## 0) Design Pillars
1. **Influence > control:** You place signals; agents decide. No direct steering.
2. **Watch to win:** Observing patterns and timing interventions beats spammy actions.
3. **Learning across runs:** Season-to-season transfer makes mastery feel earned.
4. **Readable complexity:** Clear overlays (flows, predators, cohesion) expose the system.
5. **Short loops, long arcs:** A single contract is 5–12 minutes; meta evolution lasts hours.

---

## 1) Mode Structure
- **Campaign (primary):** 5 worlds × 4 contracts = **20 levels**. Each contract has targets and constraints. You get 1–3 stars.
- **Endless Season (secondary):** Score-chase; no win state, but failure states apply. Unlocks after World 2.

### Level Flow (Campaign)
1. Briefing → 2. Planning (place pre-season signals, choose loadout) → 3. Season runs (1–3 seasons allowed) → 4. Debrief (results, stars, DNA gains).

---

## 2) Core Systems

### 2.1 Agents (Birds)
- **Count:** 80–300 depending on level.
- **State (per agent):**
  - Position (x,y), Velocity (vx,vy)
  - Energy (0–100)
  - Stress (0–100)
  - Genome (policy weights id, exploration rate, risk bias)
  - Social memory (recent neighbors’ mean heading & cohesion)
- **Sensing (each tick):** 8 raycasts (food, light, predator risk, wind), local density, neighbor velocity alignment, gradient from active signals, map hazards mask.
- **Action space:** Desired acceleration vector (dx,dy) ∈ [−a_max, a_max], altitude band (0~2 discrete; prototype 2D ignores altitude), formation stickiness (0..1).

### 2.2 Environment
- **Map:** 2D continuous world (2000×1200 world units), rendered to screen-space; obstacles, roosts, hazards, wind vectors, predator zones, light-pollution traps, protected areas.
- **Fields:**
  - **Wind:** Vector field W(x,y).
  - **Food/Nectar:** Scalar field F(x,y) with depletion.
  - **Risk:** Scalar field R(x,y) (predator density, traps).
  - **Light/Sound:** Emitted by player beacons; decay with distance and time.
- **Time:** Discrete ticks; **60 ticks/second** sim; **1 in-game day = 6000 ticks (100s)**.
- **Season:** Level allows 1–3 seasons. **Season length:** 5–12 days depending on contract.

### 2.3 Player “Signals” (Beacons & Pulses)
- **Beacon types (place on map; limited budget):**
  1. **Light Beacon** — draws birds at night; radius 150; cost 1; half-life 1.5 days.
  2. **Sound Beacon** — increases cohesion weight locally; radius 180; cost 1; half-life 1.0 day.
  3. **Food Scent** — biases foraging path; radius 120; cost 2; half-life 0.8 day; consumes food stock.
  4. **Wind Lure** — slightly boosts effective tailwind vector; radius 200; cost 2; half-life 1.0 day; limited per level.
- **Pulses (timed, cooldown; no placement):**
  - **Festival Pulse:** +reward multiplier in 220 radius for 12h; cooldown 1 day; limited uses.
  - **Scouting Ping:** Reveals fog in 200 radius for 24h; small risk spike due to noise.

### 2.4 Cohesion & Diversity Metrics
- **Cohesion (C):** Mean pairwise proximity and heading alignment (normalized 0..1). We compute:
  - Alignment order parameter A = || (1/N) Σ v̂_i ||
  - Proximity term P = mean over agents of exp(−dist_to_local_centroid / σ)
  - C = 0.6·A + 0.4·P
- **Genetic diversity (G):** Entropy over genome clusters (k-means on policy hash). Normalize 0..1.

### 2.5 Rewards (for learning)
- **Per-tick shaped reward:** r = +α·energy_norm + β·cohesion_local − γ·risk_local − δ·detour_cost
- **Event rewards:** +R_arrival per bird at roost; −R_death on loss; +R_forage on food discovery; +R_migration_speed per day early.
- Default weights (prototype): α=0.2, β=0.4, γ=0.3, δ=0.1; R_arrival=+5, R_death=−8.

### 2.6 Failure Conditions (any time)
- **Extinction:** population < N_min.
- **Cohesion collapse:** C < C_min for K=600 consecutive ticks (10s real-time).
- **Protected-zone catastrophe:** deaths_in_protected ≥ P_cap within current season.
- **Contract strikes:** End a season without meeting all targets → +1 strike; **3 strikes = contract fail**.

---

## 3) Machine Learning

### 3.1 Policy & Observations
- **Policy:** MLP (input→64→64→2) with Tanh; outputs desired acceleration vector; action noise ε ~ N(0,σ^2).
- **Obs vector (~32 dims):** local velocity, 8 raycasts for F/R/light/wind, neighbor stats (density, avg heading), signal gradients, time-of-day sin/cos, remaining season time.

### 3.2 Training Regime (prototype)
- **Online RL within season:** PPO-lite (clipped surrogate, value head), updates every 2048 steps in background thread; lr=3e-4; γ=0.98; λ=0.95; batch=1024; epochs=4.
- **Between-season boost:**
  - **Neuroevolution (ES):** Top-K elites from last season mutate (+5% of params), evaluate quick 1-day rollouts, replace bottom performers.
  - **Population-Based Training (PBT):** Perturb lr/entropy coeff per lineage.
  - **Distillation:** Teacher ensemble → student reset for newborn cohort (speeds early learning).
- **Acceleration knobs:** If player earns 3-star surplus, increase distillation weight next contract.

### 3.3 Determinism & Seeds
- Fixed RNG seed per attempt for reproducibility; store seeds per season and per hazard roll. Deterministic physics & action application; stochasticity gated to policy sampling and hazard spawns.

---

## 4) UX / UI

### 4.1 Primary HUD
- **Top bar:** Season clock (day:hour), wind indicator, weather forecast icons (next 24h), strike counter.
- **Left panel (Beacons):** Slots with counts; drag to place; right-click remove; tooltips show radius/half-life.
- **Right panel (Telemetry):**
  - Population, arrivals, deaths.
  - Cohesion meter (with thresholds lines C_min, target C*).
  - Diversity meter G.
  - Beacon budget remaining.
- **Bottom strip:** Overlays toggles (Wind, Risk, Light, Paths, Heatmap), Speed (Pause/1×/2×/4×), Pulses (Festival, Scout) with cooldown rings.
- **Minimap:** Fog-of-war; revealed areas persist per contract.

### 4.2 Placement & Feedback
- Ghost preview circles with falloff ring; decay timer arc on beacon icons; on-hover field contribution vector (tiny arrows) for local effect.
- On contract target hover: shows current vs target and projected (with 80% CI) based on current model.

### 4.3 Menus & Flow
- **Briefing:** Map vignette, targets, constraints, hazards list with probabilities.
- **Debrief:** Stars earned, surplus breakdown, DNA tokens gained, replay highlights (novelty spikes).

### 4.4 Accessibility
- Colorblind-safe palettes; adjustable UI scale; simplified overlays; reduced motion option; high-contrast mode; remappable keys.

---

## 5) Audio / Look & Feel

### 5.1 Visual Style
- Clean, minimal, data-viz inspired with soft gradients for fields; birds as luminous glyphs with small motion trails; beacons as pulsing icons. Night/day palette shifts.
- Particle effects: micro-sparks for cohesion gains; red wisps at risk zones.

### 5.2 Audio
- Ambient wind/waves; subtle musical layers tied to cohesion: higher C brings harmonic pads; deaths introduce dissonant ticks; festival pulses add percussive shimmer.

---

## 6) Content — 20-Level Campaign
**Worlds:** 1) Prairie Run, 2) Ridge Pass, 3) Coast of Lights, 4) Falcon Corridor, 5) Arctic Dash.

### 6.1 Global Parameter Defaults (per difficulty tier)
- **N_min (extinction):** 30 (W1–W2), 40 (W3–W4), 50 (W5)
- **C_min (collapse):** 0.30 (W1), 0.40 (W2), 0.45 (W3), 0.50 (W4), 0.55 (W5)
- **P_cap (protected deaths):** 20 (W3+ if protected areas exist)
- **Seasons allowed per contract:** 2 (W1–W2), 2–3 (W3–W5, listed per level)

### 6.2 Level Table (targets per contract)
**Legend:** D=distance to roost (km-equivalent), T=Time limit (days), A=Arrivals ≥, B=Beacons ≤, C*=Avg Cohesion ≥, L=Losses ≤, G*=Diversity ≥, SA=Seasons allowed.

| # | World & Name | D | T | A | B | C* | L | G* | Hazards / Notes | SA |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | W1-1 *First Flight* | 40 | 6 | 70 | 6 | 0.55 | 20 | — | Gentle wind; few predators | 2 |
| 2 | W1-2 *Grassland Glide* | 55 | 7 | 90 | 6 | 0.58 | 25 | — | Crosswind pockets | 2 |
| 3 | W1-3 *River Mirror* | 60 | 7 | 100 | 5 | 0.60 | 22 | — | River bends (risk if low altitude) | 2 |
| 4 | W1-4 *Dusk Run* | 70 | 8 | 110 | 5 | 0.62 | 22 | — | Night travel bonus with Light beacons | 2 |
| 5 | W2-1 *Ridge Pass* | 80 | 8 | 120 | 5 | 0.62 | 25 | — | Updrafts but heavy crosswinds | 2 |
| 6 | W2-2 *Saddle Storm* | 85 | 8 | 120 | 5 | 0.64 | 25 | — | 30% chance day-3 storm | 2 |
| 7 | W2-3 *Twin Valleys* | 90 | 9 | 130 | 5 | 0.65 | 26 | 0.20 | Two viable routes; diversity floor | 2 |
| 8 | W2-4 *Cold Morning* | 95 | 9 | 135 | 4 | 0.66 | 26 | 0.22 | Morning chill reduces energy regen | 2 |
| 9 | W3-1 *Harbor Glow* | 100 | 9 | 140 | 5 | 0.66 | 24 | — | Light-pollution traps on coast | 2 |
|10 | W3-2 *Lighthouse Line* | 110 |10 | 150 | 5 | 0.67 | 24 | 0.24 | Must thread lighthouse corridors | 2 |
|11 | W3-3 *Fog Banks* | 115 |10 | 155 | 5 | 0.68 | 24 | 0.25 | Heavy fog; scouting recommended | 3 |
|12 | W3-4 *Protected Cliffs* | 120 |10 | 160 | 4 | 0.68 | 22 | 0.26 | **Protected zone** beneath cliffs (P_cap=20) | 3 |
|13 | W4-1 *Falcon Corridor* | 125 |10 | 165 | 5 | 0.69 | 20 | 0.26 | Predator hotspots move daily | 2 |
|14 | W4-2 *Ambush Plains* | 130 |10 | 170 | 5 | 0.70 | 20 | 0.28 | Random predator blooms (15%/day) | 2 |
|15 | W4-3 *Feast & Flight* | 135 |11 | 180 | 5 | 0.70 | 20 | 0.30 | Rich food fields tempt detours | 3 |
|16 | W4-4 *Red Sky* | 140 |11 | 185 | 4 | 0.72 | 18 | 0.30 | Storm line on day 5 guaranteed | 3 |
|17 | W5-1 *Frozen Window* | 150 |9 | 190 | 4 | 0.73 | 18 | 0.32 | Short season; tailwind window | 3 |
|18 | W5-2 *Aurora Drift* | 160 |9 | 195 | 4 | 0.74 | 18 | 0.34 | Night-only safe; light helps | 3 |
|19 | W5-3 *Whiteout Veil* | 165 |10 | 200 | 4 | 0.75 | 16 | 0.34 | Random whiteouts (vision↓) | 3 |
|20 | W5-4 *Final Ascent* | 180 |10 | 210 | 4 | 0.76 | 16 | 0.36 | All hazards active; strict caps | 3 |

**Star scoring (per contract):**
- **3★:** Meet all targets with ≥10% surplus on *two or more* tracked metrics (time, arrivals, cohesion) **and** unused ≥1 beacon.
- **2★:** Meet all targets with ≥5% surplus on any *one* metric.
- **1★:** Meet all targets exactly (no surplus required).

**Instant fail triggers per table:** Extinction (<N_min), Cohesion collapse (C<C_min for 10s), Protected deaths≥P_cap (levels with protected areas).

---

## 7) Systems Detail

### 7.1 Physics & Ticking
- Fixed-step at 60Hz. Semi-implicit Euler. Max speed v_max; steering clamp a_max.
- Collision avoidance uses small repulsion forces around obstacles; birds pass over shallow terrain but not cliffs.

### 7.2 Beacons Model
- Each beacon adds a potential field φ_type(x,y,t) with radial falloff exp(−r/ρ). The per-agent utility adds λ_type·φ at sensor fusion. Decays per half-life via e^{−t/τ}.
- Stacking: diminishing returns (cap per type per area).

### 7.3 Hazards
- **Predators:** Poisson spawns in hotspot polygons; kill chance per tick as function of density & cohesion (higher C lowers risk).
- **Storms:** Apply wind shocks and visibility penalties; planned vs random (per level). Telegraph via forecast panel.
- **Light pollution:** Risk increases at night near cities unless cohesion≥0.7.

### 7.4 Energy & Foraging
- Energy drains with speed^2; regen at roost/forage patches. Low energy increases detour weight, reduces max speed.

### 7.5 Fog-of-War
- Hidden fields for risk/wind until revealed by proximity or scouting. Knowledge persists within the contract.

---

## 8) Tech Architecture

### 8.1 Stack
- **Sim/ML:** Python 3.11, NumPy, PyTorch.
- **Client:** React + Canvas/WebGL (PixiJS or ThreeJS 2D layer). Electron (desktop) optional.
- **IPC:** WebSocket (localhost) or WebRTC DataChannel for live-coding sessions.
- **Authoring:** Level JSON schema; content hot-reload.

### 8.2 Process Model
- Sim runs in a Python process; pushes state deltas (50–100ms) to client. Client interpolates for 60fps.
- Background thread for PPO updates; season breaks for ES/PBT steps.

### 8.3 Performance Targets (prototype)
- 300 agents at 60Hz on a modern laptop CPU; policy forward pass batched on CPU/GPU.
- State delta payload ≤ 30 KB / 100ms; server <10% CPU on 8-core.

### 8.4 Determinism & Replays
- Log seeds, hazard rolls, player actions timeline. Re-sim deterministically for replays.

### 8.5 Data & Save
- **RunSave**: {seed, level_id, attempts, stars, DNA_tokens, elite_snapshots[], discovered_codex[]}
- **PolicySnapshot**: {weights, hyperparams, fitness, lineage_id, timestamp}

---

## 9) Level/Contract Schema
```json
{
  "id": "W3-4",
  "name": "Protected Cliffs",
  "distance_km": 120,
  "time_limit_days": 10,
  "targets": {
    "arrivals_min": 160,
    "cohesion_avg_min": 0.68,
    "losses_max": 22,
    "diversity_min": 0.26,
    "beacon_budget_max": 4
  },
  "seasons_allowed": 3,
  "hazards": {
    "predator_hotspots": 3,
    "storms": {"planned_days": [5], "random_daily_prob": 0.0},
    "protected_zones": [{"polygon": "cliff_poly_01", "death_cap": 20}],
    "light_pollution": false
  },
  "notes": "Fog and vertical cliffs; scout early; avoid protected shelf."
}
```

---

## 10) Prototype Build Plan (4 slices)
1. **Slice A — Flock Sandbox (Week 1):** 2D sim, 200 agents, beacons (light/sound), wind/risk fields, overlays, basic HUD. No ML; scripted boids.
2. **Slice B — Online RL (Week 2):** Swap boids steering for policy; per-tick rewards; PPO-lite; one contract playable.
3. **Slice C — Seasons & Evolution (Week 3):** Season loop, ES/PBT between seasons, meta-progression save, 4 contracts.
4. **Slice D — Content & Polish (Week 4):** Full 20 levels, audio layers, replay, star scoring, accessibility.

---

## 11) Tuning & Telemetry
- **Dashboards:**
  - Learning curve: reward per episode & arrivals.
  - Difficulty: fail rates, time-to-first-win per level.
  - Cohesion timeline & collapse incidents.
- **Auto-balancing hooks:** Adjust predator spawn rate to hit 40–60% first-try fail on W3+; beacon budgets tuned to create 2–3 meaningful decisions/season.

---

## 12) APIs & Pseudocode

### 12.1 Level Loading
```python
@dataclass
class Targets:
    arrivals_min: int
    cohesion_avg_min: float
    losses_max: int
    diversity_min: float | None
    beacon_budget_max: int

@dataclass
class Contract:
    id: str
    name: str
    distance_km: float
    time_limit_days: int
    seasons_allowed: int
    hazards: dict
    targets: Targets

current_contract: Contract = load_contract(json_path)
```

### 12.2 Tick Loop
```python
def tick(dt=1/60):
    apply_hazards()
    obs = observe(batch_agents)
    actions = policy.forward(obs) + noise()
    integrate(batch_agents, actions, dt)
    r = compute_rewards(batch_agents)
    buffer.add(obs, actions, r)
    if buffer.size >= PPO_STEPS:
        ppo_update(buffer)
```

### 12.3 Cohesion & Collapse
```python
def cohesion_metrics(agents):
    v = normalize(agents.v)
    A = np.linalg.norm(v.mean(axis=0))
    P = np.mean(np.exp(-dist_to_centroid(agents)/SIGMA))
    return 0.6*A + 0.4*P

if C < C_MIN:
    collapse_ticks += 1
    if collapse_ticks >= 600:
        fail("Cohesion collapse")
else:
    collapse_ticks = 0
```

### 12.4 Star Scoring
```python
def star_rating(results, targets):
    surplus = {
        'time': (targets.time_limit_days - results.days_used)/targets.time_limit_days,
        'arrivals': (results.arrivals - targets.arrivals_min)/targets.arrivals_min,
        'cohesion': (results.cohesion_avg - targets.cohesion_avg_min)/targets.cohesion_avg_min,
        'beacons': (targets.beacon_budget_max - results.beacons_used)/max(1, targets.beacon_budget_max)
    }
    surplus_hits = sum(v >= 0.10 for v in surplus.values() if not np.isnan(v))
    if results.met_all_targets and surplus_hits >= 2 and surplus['beacons'] >= 0.10:
        return 3
    if results.met_all_targets and any(v >= 0.05 for v in surplus.values()):
        return 2
    return 1 if results.met_all_targets else 0
```

### 12.5 Beacon Field
```python
def beacon_field(xy, beacons, t):
    total = np.zeros_like(xy)
    for b in beacons:
        r = np.linalg.norm(xy - b.pos, axis=1)
        w = np.exp(-r/b.rho) * np.exp(-(t-b.t0)/b.tau)
        total += (b.vector_dir * w[:,None]) if b.type=='wind' else (w[:,None])
    return total.clip(-MAX_FIELD, MAX_FIELD)
```

---

## 13) QA Checklist (per level)
- Can a first-time player pass within 3 attempts using 80% of beacon budget?
- Does scouting meaningfully reveal at least 2 hazards?
- Are random hazards telegraphed ≥12h ahead in-UI?
- Does 3★ require deliberate surplus, not luck?

---

## 14) Future Extensions
- Morphological mutations (wing loading → different flight profiles)
- Altitude bands with thermal columns
- Photo mode & shareable replays
- Scenario editor

---

**End of v0.1**

