from collections import defaultdict

from fastapi import WebSocket


class IncidentLocationConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, incident_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[incident_id].add(websocket)

    def disconnect(self, incident_id: int, websocket: WebSocket) -> None:
        if incident_id not in self._connections:
            return
        self._connections[incident_id].discard(websocket)
        if not self._connections[incident_id]:
            self._connections.pop(incident_id, None)

    async def send_personal_message(self, websocket: WebSocket, payload: dict) -> None:
        await websocket.send_json(payload)

    async def broadcast_incident_update(self, incident_id: int, payload: dict) -> None:
        stale_connections: list[WebSocket] = []
        for websocket in self._connections.get(incident_id, set()):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(incident_id, websocket)


incident_location_manager = IncidentLocationConnectionManager()
