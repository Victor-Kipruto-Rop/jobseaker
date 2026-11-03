# Local development

1. Install Docker Desktop, Python 3.12+, Node.js 20+, and pnpm 9+.
2. Copy `.env.example` to `.env`.
3. Set a random `APP_SECRET_KEY`; leave provider keys empty for mock mode.
4. Run `docker compose -f infrastructure/compose/docker-compose.yml up --build`.
5. Open http://localhost:3000 and http://localhost:8000/docs.
6. Stop with `docker compose -f infrastructure/compose/docker-compose.yml down`.

Named volumes preserve local state. Use `down -v` only when intentionally deleting local data.
