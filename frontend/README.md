# AgentShield Console

React dashboard for the AgentShield FastAPI service.

## Run locally

Start the backend first on port `8000`, then:

```bash
npm install
npm run dev
```

Open `http://localhost:5173`.

The Vite development server proxies `/api` requests to `http://localhost:8000`. To point at another backend in a deployed build, set `VITE_API_URL` to the API base URL, for example `http://localhost:8000`.

## Connected API routes

- `GET /health` for dependency status
- `GET /security/attack-cases` for the attack catalog
- `POST /security/attack-suite` for before/after defense evaluation
- `POST /chat` for the agent conversation
