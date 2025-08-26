# Murmuration Genetic Evolution System

## Overview

The genetic system transforms Murmuration from a breed-level evolution game into a true genetic simulation where individual birds have unique DNA, genders, and family lineages. Birds that survive levels pair up to produce offspring that inherit traits from both parents.

## Core Mechanics

### 1. Starting Population
- **100 birds**: 50 males (♂), 50 females (♀)
- Each bird has **individual genetics** with 9 traits
- Random trait distribution for Generation 0

### 2. Individual Genetics

Each bird has unique genetics that affect gameplay:

#### Core Traits (0-1 scale)
- **Hazard Awareness**: How early they detect dangers
- **Energy Efficiency**: How slowly they consume energy
- **Flock Cohesion**: How well they stick with the group
- **Beacon Sensitivity**: How well they respond to player guidance
- **Stress Resilience**: How well they handle threats

#### Physical Traits
- **Size Factor** (0.8-1.2): Affects visual size
- **Speed Factor** (0.9-1.1): Affects maximum velocity

#### Hidden Traits
- **Fertility** (0.8-1.0): Chance to successfully breed
- **Longevity** (0.8-1.0): Resistance to exhaustion

### 3. Breeding System

After completing a level:

1. **Survivors Pair Up**
   - Only birds that survived can breed
   - One male + one female = one offspring
   - Unpaired birds don't reproduce

2. **Genetic Inheritance**
   - Each trait has 50% chance from each parent
   - 30% chance of blending both parents' values
   - Small mutations (±5%) for variation
   - Physical traits tend to blend more

3. **Next Generation**
   - Population = Survivors + Offspring
   - Each bird tracks its generation number
   - Family connections maintained

### 4. Visual Feedback

#### Gender Indicators
- **Males**: Blue-tinted birds (♂)
- **Females**: Pink-tinted birds (♀)
- Size varies based on genetics

#### Family Visualization
- Subtle lines connect breeding pairs
- Generation number displayed (G0, G1, G2...)
- Selected birds show family tree

#### Population Statistics
- **Trait Bars**: Show population averages
- **Diversity Meter**: Genetic variation indicator
- **Population Pyramid**: Gender/generation distribution
- **Hall of Fame**: Top breeding bloodlines

### 5. Gameplay Impact

#### Strategic Breeding
- **Save Your Best**: Strong birds should survive to breed
- **Gender Balance**: Losing too many of one gender limits reproduction
- **Genetic Bottlenecks**: Few survivors = potential inbreeding
- **Hybrid Vigor**: Diverse parents produce stronger offspring

#### Trait Effects in Game
- High **Hazard Awareness** → Earlier predator detection
- High **Energy Efficiency** → Slower energy drain
- High **Flock Cohesion** → Better group survival
- High **Beacon Sensitivity** → Better player control
- High **Stress Resilience** → Less panic, better under pressure

### 6. Statistics & Tracking

#### Population Genetics Dashboard
- Average trait values across population
- Genetic diversity index
- Trait variance indicators

#### Family Trees
- Click any bird to see lineage
- Parents, offspring, partners displayed
- Up to 3 generations shown

#### Top Bloodlines
- Birds ranked by successful offspring
- Champion dynasties tracked
- Fitness scores calculated

## Example Breeding Scenario

**Level Complete:**
- Started: 100 birds (50♂, 50♀)
- Survived: 70 birds (35♂, 35♀)
- Lost: 30 birds

**Breeding Phase:**
- 35 pairs formed
- 35 offspring created (random genders)
- New population: 70 survivors + 35 babies = 105 birds

**Genetic Changes:**
- Birds that avoided predators → offspring with better awareness
- Birds that conserved energy → offspring with better efficiency
- Random mutations add variety

## Files & Implementation

### Core Files
- `sim/simulation_genetic.py` - Complete genetic system
- `demo_genetic.html` - Rich UI with all visualizations
- `sim/server.py` - WebSocket support for genetic mode

### Key Classes
- `Genetics` - Individual trait storage
- `BirdEntity` - Extended bird with family tracking
- `GeneticSimulation` - Main game loop with breeding
- `PopulationStats` - Aggregate statistics

## How to Play

1. **Connect** to server
2. **Start** with 100 birds (50/50 gender split)
3. **Guide** flock through hazards using beacons
4. **Complete** level with as many survivors as possible
5. **Breed** survivors to create next generation
6. **Continue** with improved population
7. **Goal**: Create ultimate genetic lineage!

## Future Enhancements

- **Dominant/Recessive** genes
- **Genetic diseases** that skip generations
- **Crossover** between chromosomes
- **Sexual selection** (birds choose mates)
- **Epigenetics** (environmental factors affect genes)
- **Gene editing** tools for players
- **Genetic tournaments** between players' populations

## Commands

```bash
# Start the genetic game server
python -m sim.server

# Open the genetic UI
open demo_genetic.html
```

The genetic system adds deep strategy to Murmuration - it's not just about surviving one level, but building a dynasty of birds that gets stronger with each generation!