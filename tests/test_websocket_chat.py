import unittest

from horbot.web import websocket as websocket_module


class FakeWebSocket:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.payloads.append(payload)


class WebSocketBroadcastTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        websocket_module.websocket_connections.clear()
        websocket_module.session_subscriptions.clear()
        websocket_module.connection_subscriptions.clear()

    async def asyncTearDown(self) -> None:
        websocket_module.websocket_connections.clear()
        websocket_module.session_subscriptions.clear()
        websocket_module.connection_subscriptions.clear()

    async def test_broadcast_to_session_includes_session_key(self):
        fake_websocket = FakeWebSocket()
        websocket_module.websocket_connections["conn-1"] = fake_websocket
        websocket_module.session_subscriptions["web:team_team-001"] = {"conn-1"}
        websocket_module.connection_subscriptions["conn-1"] = {"web:team_team-001"}

        await websocket_module.broadcast_to_session(
            "web:team_team-001",
            {"event": "progress", "content": "relay"},
        )

        self.assertEqual(
            fake_websocket.payloads,
            [{
                "event": "progress",
                "content": "relay",
                "session_key": "web:team_team-001",
            }],
        )


if __name__ == "__main__":
    unittest.main()
