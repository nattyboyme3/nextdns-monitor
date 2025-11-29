# nextdns_stream.py

import time
import json
import logging
from typing import Optional, Iterator, Dict, Any
from dataclasses import dataclass
import requests
from requests.exceptions import RequestException
import sseclient  # install via `pip install sseclient-py`

# Logging setup (you can configure as you see fit)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

@dataclass
class DeviceInfo:
    id: str
    name: Optional[str] = None
    model: Optional[str] = None

@dataclass
class NextDNSLog:
    event_id: str
    timestamp: str
    domain: Optional[str]
    root: Optional[str]
    encrypted: bool
    protocol: Optional[str]
    client_ip: Optional[str]
    client: Optional[str]
    device: Optional[DeviceInfo]
    status: Optional[str]
    reasons: list[Dict[str, Any]]
    raw: Dict[str, Any]

class NextDNSStreamClient:
    def __init__(self, api_key: str, profile_id: str, base_url: str = "https://api.nextdns.io"):
        self.api_key = api_key
        self.profile_id = profile_id
        self.base_url = base_url.rstrip("/")
        self._last_event_id: Optional[str] = None
        self._session = requests.Session()
        self._headers = {
            "X-Api-Key": self.api_key,
            "Accept": "text/event-stream"
        }

    def _build_stream_url(self) -> str:
        return f"{self.base_url}/profiles/{self.profile_id}/logs/stream"

    def _build_params(self) -> Dict[str, str]:
        params: Dict[str, str] = {}
        if self._last_event_id:
            params["id"] = self._last_event_id
        return params

    def stream(self, params: Optional[Dict[str, str]] = None, retry_delay: float = 5.0) -> Iterator[NextDNSLog]:
        """
        Returns a generator of NextDNSLog objects as events arrive.
        If the connection drops, it will wait `retry_delay` seconds and attempt to reconnect,
        resuming from the last received event id.
        `params` allows filtering (see NextDNS API docs) — e.g. {"status": "blocked"}.
        """
        while True:
            url = self._build_stream_url()
            query = self._build_params()
            if params:
                query.update(params)

            try:
                logger.info(f"Connecting to NextDNS stream: {url}  params={query}")
                resp = self._session.get(url, headers=self._headers, params=query, stream=True, timeout=60)
                resp.raise_for_status()
                client = sseclient.SSEClient(resp)
                for event in client.events():
                    if not event.data:
                        continue
                    data = json.loads(event.data)
                    log = self._parse_event(event.id, data)
                    self._last_event_id = event.id
                    yield log
            except RequestException as e:
                logger.warning(f"Error connecting/reading from stream: {e}. Retrying after {retry_delay}s...")
                time.sleep(retry_delay)
                continue
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                time.sleep(retry_delay)
                continue

    def _parse_event(self, event_id: str, obj: Dict[str, Any]) -> NextDNSLog:
        device = None
        if obj.get("device") is not None:
            dev = obj["device"]
            device = DeviceInfo(
                id=dev.get("id"),
                name=dev.get("name"),
                model=dev.get("model"),
            )
        return NextDNSLog(
            event_id=event_id,
            timestamp=obj.get("timestamp"),
            domain=obj.get("domain"),
            root=obj.get("root"),
            encrypted=bool(obj.get("encrypted", False)),
            protocol=obj.get("protocol"),
            client_ip=obj.get("clientIp"),
            client=obj.get("client"),
            device=device,
            status=obj.get("status"),
            reasons=obj.get("reasons", []),
            raw=obj,
        )

    def close(self):
        self._session.close()
