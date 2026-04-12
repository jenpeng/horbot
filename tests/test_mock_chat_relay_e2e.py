import unittest

from horbot.testing.mock_chat_relay import (
    run_mock_multi_agent_relay_stream_test,
    run_mock_relay_stream_test,
)


class MockChatRelayE2ETests(unittest.IsolatedAsyncioTestCase):
    async def test_mock_relay_stream_runs_alpha_beta_alpha(self):
        result = await run_mock_relay_stream_test()

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["agent_start_sequence"], ["alpha", "beta", "alpha"])
        self.assertEqual(
            result["agent_done_sequence"],
            [
                ["alpha", "@Beta 接力第一跳"],
                ["beta", "@Alpha 接力回给你"],
                ["alpha", "接力完成2"],
            ],
        )
        self.assertEqual(
            result["mention_sequence"],
            [["alpha", "beta"], ["beta", "alpha"]],
        )

    async def test_mock_multi_agent_relay_stream_runs_all_handoffs(self):
        result = await run_mock_multi_agent_relay_stream_test()

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(
            result["agent_start_sequence"],
            ["alpha", "beta", "gamma", "delta", "alpha"],
        )
        self.assertEqual(
            result["mention_sequence"],
            [
                ["alpha", "beta"],
                ["alpha", "gamma"],
                ["alpha", "delta"],
                ["beta", "alpha"],
                ["gamma", "alpha"],
                ["delta", "alpha"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
