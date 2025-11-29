# NextDNS Monitor

Automated monitoring tool for NextDNS logs. Analyzes DNS activity, detects suspicious requests, monitors specific domains, and identifies network gaps. Sends daily email summaries.

## Features

- **Suspicious Activity Detection**: Flags requests in critical categories (malware, phishing, porn, etc.)
- **Domain Monitoring**: Tracks access to specific domains of interest
- **Gap Analysis**: Identifies network outages (devices with no DNS activity for extended periods)
- **Daily Email Reports**: Automated summaries with color-coded alerts (🔴 Critical, 🟠 Warnings, 🟢 All Clear)

## Quick Start

### Using Docker (Recommended)

```bash
# Pull the image
docker pull ghcr.io/nattyboyme3/nextdns-monitor:latest

# Create .env file (see Configuration below)
# Run
docker run --rm --env-file .env ghcr.io/nattyboyme3/nextdns-monitor:latest
```

### Using Docker Compose

```bash
./docker-launch.sh
```

### Local Python

```bash
pip install -r requirements.txt
python main.py
```

## Configuration

Create a `.env` file:

```env
# NextDNS API credentials
API_KEY=your_nextdns_api_key
PROFILE_ID=your_profile_id

# Monitoring rules
CRITICAL_CATEGORIES=Porn,Malware,Phishing
WARNING_DOMAINS=reddit.com,twitter.com
GAP_MINUTE_THRESHOLD=60

# Email settings
FROM_EMAIL=sender@gmail.com
TO_EMAIL=recipient1@example.com,recipient2@example.com
APP_PASSWORD=gmail_app_password
TIMEZONE=America/New_York
```

### Get NextDNS Credentials

1. **API Key**: https://my.nextdns.io/account
2. **Profile ID**: Found in your NextDNS configuration URL (`https://my.nextdns.io/XXXXXX/setup`)

### Gmail App Password

1. Enable 2FA on your Google account
2. Generate app password: https://myaccount.google.com/apppasswords

## Automation

### Cron (Daily at Midnight)

```bash
crontab -e
```

Add:
```
0 0 * * * cd /path/to/nextdns-monitor && /usr/local/bin/docker run --rm --env-file .env ghcr.io/nattyboyme3/nextdns-monitor:latest >> /var/log/nextdns-monitor.log 2>&1
```

### GitHub Actions

See `DOCKER_PUBLISH.md` for automated image publishing.

## Development

```bash
# Build locally
docker build -t nextdns-monitor .

# Publish to GitHub Container Registry
./docker-publish.sh latest --push
```

See `DOCKER_PUBLISH.md` for detailed publishing instructions.

## Requirements

- NextDNS account with API access
- Gmail account (or SMTP server) for email notifications
- Docker (recommended) or Python 3.11+

## License

MIT