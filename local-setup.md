# Local Firecrawl Setup Guide

## Prerequisites

- Docker and Docker Compose installed
- At least 4GB RAM available
- 10GB free disk space

## Quick Start

### Using Makefile (Recommended)

```bash
make setup
```

This runs the complete setup: install dependencies, initialize Firecrawl, build, and start services.

**Verify installation:**
```bash
make test
```

**Run scraper:**
```bash
make scrape
```

**Stop services:**
```bash
make firecrawl-stop
```

**View all commands:**
```bash
make help
```

### Manual Setup (Alternative)

### 1. Build and Start Firecrawl Services

```bash
cd firecrawl-local
docker compose build
docker compose up -d
```

**First build takes 5-10 minutes.** Subsequent starts are instant.

### 2. Verify Services Are Running

```bash
docker compose ps
```

All services should show "Up" status.

Test the API:
```bash
curl http://localhost:3002/v2/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com", "formats": ["markdown"]}'
```

Expected: JSON response with scraped content.

### 3. Run Your Scraper

```bash
cd ..
python scraper.py
```

### 4. Stop Services When Done

```bash
cd firecrawl-local
docker compose down
```

## Configuration

Firecrawl configuration is in `firecrawl-local/.env`

Current settings:
- Port: 3002
- Authentication: Disabled
- Logging: INFO level

### Optional Features

Edit `firecrawl-local/.env` to enable:

```bash
OPENAI_API_KEY=your_key
PROXY_SERVER=your_proxy
```

After changes:
```bash
cd firecrawl-local
docker compose restart
```

## Troubleshooting

### Build Fails

```bash
cd firecrawl-local
docker compose down -v
docker compose build --no-cache
```

### Services Won't Start

```bash
cd firecrawl-local
docker compose logs -f
```

Look for error messages in the logs.

### API Not Responding

```bash
cd firecrawl-local
docker compose restart api
```

### Port Conflicts

If port 3002 is in use, edit `firecrawl-local/.env`:
```bash
PORT=3003
```

Then restart:
```bash
docker compose down
docker compose up -d
```

Update scraper to use new port in `.env`:
```bash
FIRECRAWL_API_URL=http://localhost:3003
```

### Reset Everything

```bash
cd firecrawl-local
docker compose down -v
docker compose build
docker compose up -d
```

## Monitoring

### View Logs

```bash
cd firecrawl-local
docker compose logs -f api
docker compose logs -f redis
docker compose logs -f playwright-service
```

### Check Resource Usage

```bash
docker stats
```

### Queue Admin Panel

Visit: http://localhost:3002/admin/@/queues

Default credentials in `firecrawl-local/.env`: BULL_AUTH_KEY

## System Requirements

### Minimum
- 4GB RAM
- 2 CPU cores  
- 5GB disk space
- Docker 20.10+
- Docker Compose 2.0+

### Recommended
- 8GB RAM
- 4 CPU cores
- 10GB disk space
