```bash
docker build --build-arg ENVIRONMENT=LOCAL -t gpw-scraper:latest .
docker compose -f docker-compose.yaml -f compose.dev.yaml up
docker exec gpw-scraper pytest -vv
```
