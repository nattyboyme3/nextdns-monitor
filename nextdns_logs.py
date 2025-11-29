# nextdns_fetch_logs.py

import requests
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

@dataclass
class NextDNSLog:
    timestamp: str
    # include a catch-all raw dict so you don’t lose unexpected fields
    raw: Dict[str, Any] = field(default_factory=dict)
    # (optional) parsed convenience fields
    domain: Optional[str] = field(default=None)
    root: Optional[str] = field(default=None)
    tracker: Optional[str] = field(default=None)
    encrypted: Optional[bool] = field(default=None)
    protocol: Optional[str] = field(default=None)
    client_ip: Optional[str] = field(default=None)
    client: Optional[str] = field(default=None)
    device_name: Optional[str] = field(default=None)
    status: Optional[str] = field(default=None)
    reason_name: Optional[str] = field(default=None)
    reasons: List[Dict[str, Any]] = field(default_factory=list)

class NextDNSLogFetcher:
    def __init__(self, api_key: str, profile_id: str, base_url: str = "https://api.nextdns.io"):
        self.api_key = api_key
        self.profile_id = profile_id
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._headers = {"X-Api-Key": self.api_key}

    def _build_url(self) -> str:
        return f"{self.base_url}/profiles/{self.profile_id}/logs"

    def fetch_logs(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        per_page: int = 1000,
        max_pages: Optional[int] = None,
        delay_on_rate_limit: float = 5.0,
    ) -> List[NextDNSLog]:
        """
        Fetch logs in the given time window (ISO8601, unix timestamp, or relative).
        Returns a list of NextDNSLog objects.

        If per_page is too high you may get rate limited — adjust accordingly.
        """
        url = self._build_url()
        params: Dict[str, Any] = {
            "limit": per_page
        }
        if start:
            params["from"] = start
        if end:
            params["to"] = end

        all_logs: List[NextDNSLog] = []
        cursor: Optional[str] = None
        page = 0

        while True:
            if cursor:
                params["cursor"] = cursor

            logger.info(f"Requesting logs page {page+1} (cursor={cursor})")
            resp = self._session.get(url, headers=self._headers, params=params, timeout=60)
            if resp.status_code == 429:
                logger.warning(f"Rate limited (429). Sleeping {delay_on_rate_limit}s then retrying...")
                time.sleep(delay_on_rate_limit)
                continue
            resp.raise_for_status()
            body = resp.json()
            data = body.get("data", [])
            for obj in data:
                device_name = ""
                reason_names_str = ""
                if obj.get("reasons"):
                    reason_names = [ x.get('name') for x in obj.get("reasons", []) ]
                    reason_names_str = ", ".join(reason_names)
                if obj.get("device"):
                    d = obj["device"]
                    device_name = d.get("name")
                log = NextDNSLog(
                    timestamp=obj.get("timestamp"),
                    raw=obj,
                    domain=obj.get("domain"),
                    root=obj.get("root"),
                    tracker=obj.get("tracker"),
                    encrypted=obj.get("encrypted"),
                    protocol=obj.get("protocol"),
                    client_ip=obj.get("clientIp"),
                    client=obj.get("client"),
                    device_name=device_name,
                    reason_name=reason_names_str,
                    status=obj.get("status"),
                    reasons=obj.get("reasons", []),
                )
                all_logs.append(log)

            meta = body.get("meta", {})
            pagination = meta.get("pagination", {})
            cursor = pagination.get("cursor")
            page += 1

            if not cursor:
                logger.info("No more pages (cursor null).")
                break

            if max_pages is not None and page >= max_pages:
                logger.info(f"Reached max_pages={max_pages}, stopping early.")
                break

            # respect polite pacing
            time.sleep(0.1)

        return all_logs

    def fetch_logs_for_previous_day(self, per_page: int = 1000, tz = timezone.utc) -> List[NextDNSLog]:
        """
        Convenience method to fetch all logs from 00:00 to 23:59 of previous local day (UTC-based ISO).
        """
        now = datetime.now(tz)
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end   = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
        logger.info(f"Fetching logs from {start} to {end}")
        return self.fetch_logs(start=start, end=end, per_page=per_page)

    def close(self):
        self._session.close()
