# Sendero Portfolio

An AI-native diagnostic tool for VC/PE investment teams: is a cluster of underperforming portfolio companies a **thesis problem** (route to IC — reallocate or re-underwrite) or an **execution problem** (route to the operating partner — coach the team)? Built on Sendero's two-level statistical build-vs-training test, applied to portfolio performance data instead of enterprise-software adoption data.

## What's real vs. what's a mockup

This repo is the **working core** of the product, not the visual concept. It deliberately does one thing — upload data, run the real classification engine, get a real ranked worklist back — and nothing else yet.

**Built and working:**
- The classification engine itself (`backend/sendero_engine/classify.py`), Sendero's own two-level dispersion + cohort-explanatory statistical test.
- A Flask API (`backend/app.py`) that accepts a CSV upload, runs the real engine, stores the result, and serves a ranked worklist.
- A minimal frontend (`frontend/index.html`) that talks to that real API — no framework, just enough to demo the loop end to end.
- A real test suite (`backend/tests/test_app.py`) that exercises the actual engine, not a mock.

**Not built yet, on purpose** — see [`docs/mvp_roadmap.md`](docs/mvp_roadmap.md) for what's next and why this is the right place to start:
- AI assistant / IC memo drafting
- Cross-model verification
- Live data connectors (NetSuite, QuickBooks, etc.) — CSV upload only for now
- Box integration, in-app comments, version history
- Authentication, seats, billing, white-labeling

The full-featured version of the product — everything above, including the AI assistant, Box sync, cross-model verification, and white-labeling — exists today as **visual mockups** (published as Artifacts during product design; ask the founder for the links) that show the intended end state. This repo is the real, working foundation those mockups sit on top of.

## Quickstart

```bash
cd backend
pip install -r requirements.txt
python app.py
# API now running at http://localhost:5000
```

In a second terminal, open `frontend/index.html` directly in a browser (or serve it: `python -m http.server 8080 --directory frontend`), then upload `data/sample_digital_health_portfolio.csv` using the form defaults.

Run the tests:
```bash
cd backend
pip install pytest
python -m pytest tests/ -v
```

## How the classification works

See [`docs/classification_method.md`](docs/classification_method.md) for the full methodology (Sendero's own reference doc). Short version: for a cluster of portfolio companies, Sendero looks at whether underperformance is spread evenly across the whole group (a **build**-type, structural finding — the thesis or deal structure needs to change) or concentrated in companies that share a specific trait like inexperienced management (a **training**-type finding — coach the team, the thesis is fine). It returns a classification, a confidence score, and the statistical evidence behind the call — not just a label.

## Project structure

```
backend/
  app.py                    Flask API
  sendero_engine/
    classify.py              The classification engine (Sendero's own IP)
  tests/test_app.py          Real end-to-end tests
data/
  sample_digital_health_portfolio.csv    Sample dataset matching the product mockups
docs/
  classification_method.md   Full methodology reference
  mvp_roadmap.md              What's built, what's next, and why
frontend/
  index.html                 Minimal working UI, no build step required
```

## License / ownership

The Sendero classification methodology is proprietary, patent-pending IP. This repository and everything in it is private and unpublished — do not distribute outside the founding team without explicit sign-off.
