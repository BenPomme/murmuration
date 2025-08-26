# Murmuration Quick Start Guide

## 🚀 Running the Complete System

### 1. Install Dependencies

```bash
# Python dependencies
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
pip install websockets hypothesis

# Node dependencies (for full React client)
cd client
npm install
cd ..
```

### 2. Start the WebSocket Server

```bash
# From project root with venv activated
python -m sim.cli.main serve

# Or with custom host/port
python -m sim.cli.main serve --host 0.0.0.0 --port 8080
```

You should see:
```
🌐 Starting Murmuration WebSocket server on ws://localhost:8765
```

### 3. Run the Demo

Open `demo.html` in a web browser:
- **macOS**: `open demo.html`
- **Linux**: `xdg-open demo.html`
- **Windows**: `start demo.html`

Then:
1. Click "Connect" to establish WebSocket connection
2. Click "Load Level W1-1" to start the simulation
3. Use Pause and Speed controls

### 4. Run the Full React Client (Optional)

```bash
cd client
npm run dev
```

Navigate to http://localhost:5173 in your browser.

## 🎮 Available CLI Commands

```bash
# Run simulation headless
python -m sim.cli.main run --level W1-1 --agents 150 --seed 42

# Train ML policy
python -m sim.cli.main train --level W1-1 --epochs 10

# Run performance benchmark
python -m sim.cli.main bench --agents 300

# Run acceptance tests
python -m sim.cli.main accept --config configs/acceptance.yaml

# Replay a simulation
python -m sim.cli.main replay --from out/replay.jsonl
```

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test modules
pytest tests/test_star_scoring.py -v
pytest tests/test_physics.py -v
pytest tests/test_hazards.py -v

# Run without coverage check
pytest tests/ --no-cov
```

## 📊 System Status

✅ **Working Components:**
- Core simulation engine
- Physics system with flocking
- Hazards (predators, storms, light pollution)
- Beacon system
- Star scoring
- WebSocket server
- Basic visualization in demo.html
- 103+ tests passing

⚠️ **In Progress:**
- Full ML training (using mock torch for now)
- Complete React client integration
- Some performance optimizations

## 🐛 Troubleshooting

### WebSocket Connection Failed
- Ensure server is running: `python -m sim.cli.main serve`
- Check firewall settings for port 8765
- Try different browser if WebSocket is blocked

### Module Import Errors
- Activate virtual environment: `source venv/bin/activate`
- Reinstall dependencies: `pip install -e ".[dev]"`

### Performance Issues
- Reduce agent count in demo
- Check CPU usage during simulation
- Disable hazards for better performance

## 📚 Documentation

- [Full Design Document](murmuration_full_game_tech_design_doc_v_0.md)
- [Development Playbook](CLAUDE.md)
- [API Documentation](docs/api.md) (coming soon)

## 🎯 Next Steps

1. **Play with the demo** to see agents flocking
2. **Modify parameters** in levels/W1-1.json
3. **Create new levels** following the schema
4. **Implement beacons** in the UI
5. **Train ML policies** for smarter agents

Happy Murmurating! 🦅