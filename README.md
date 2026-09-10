# AERA Motor Copilot

AERA is an industrial AI copilot. The motor and HMI exist to demonstrate it.

They share **one real-time state**:

```
MOTOR SIMULATOR  →  SHARED STATE / EVENT BUS  →  HMI
                                          ↘
                                           AERA
                                           observe → detect → compare history
                                           → assess risk → explain → recommend
                                           → adapt if the operator cannot act
```

The operator sees **one screen**:

- **Left:** live industrial motor + HMI (start/stop/reset, live parameters)
- **Right:** AERA live copilot, event log, and historical cases

AERA does not alarm on every blip. It decides **which deviations deserve attention** using live data, rate of change, and what happened last time on this motor.

## Live

https://aera-ld9s.onrender.com

The free Render instance sleeps after idle time, so the first load can take about a minute.

## Run

```bash
./scripts/dev.sh
```

UI: http://127.0.0.1:3001  
API: http://127.0.0.1:8001/docs

Copy `.env.example` to `.env` if you want an optional LLM key. The copilot works without it.

## Deploy

Production serves the UI, `/api`, and `/ws/aera` from one process.

```bash
docker build -t aera .
docker run -p 8001:8001 aera
```

Then open http://localhost:8001

`Dockerfile`, `fly.toml`, and `render.yaml` are in the repo for Fly.io or Render.

## Demo

1. Motor is running. AERA shows **NORMAL**.
2. On the HMI, raise **LOAD**, then raise **VIB** toward 7 mm/s (or tap **Bearing**).
3. AERA moves to **HIGH RISK**, compares with 8 similar historical cases, and recommends inspecting bearing alignment.
4. Click **NOT POSSIBLE** or type `I cannot stop the motor right now.`
5. AERA gives an **alternative action** (reduce load, keep monitoring, inspect at the next safe stop).
6. Open **EVENTS** and **HISTORY** on the AERA panel — the motor and HMI stay visible.
