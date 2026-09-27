import unittest

from benchmarks.latency_test import measure_stream


class FakeResponse:
    headers = {"Server-Timing": "retrieval;dur=12.5, index;dur=1.5, vector;dur=8.0, keyword;dur=2.0, fusion;dur=0.5"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=None, decode_unicode=False):
        yield 'event: status\ndata: {"stage":"drafting","text":"Drafting"}\n\n'
        yield 'event: sources\ndata: {"sources":[]}\n\n'
        yield 'event: tok'
        yield 'en\ndata: {"text":"Hello"}\n\n'
        yield 'event: timing\ndata: {"draft_ms":150.0,"check_ms":90.0,"conflict_ms":40.0,"answer_ms":285.0,"drafts":1,"check_calls":3}\n\n'
        yield 'event: done\ndata: {}\n\n'


class FakeSession:
    def post(self, url, json, stream, timeout):
        if json != {"query": "example"} or not stream:
            raise AssertionError("The request must stream the fixed query")
        return FakeResponse()


class LatencyTests(unittest.TestCase):
    def test_measures_first_token_done_and_server_retrieval(self):
        moments = iter([10.0, 10.02, 10.1, 10.3])
        result = measure_stream(
            "example", session=FakeSession(), url="http://localhost/chat", clock=lambda: next(moments)
        )

        self.assertAlmostEqual(result["retrieval_ms"], 12.5)
        self.assertAlmostEqual(result["index_ms"], 1.5)
        self.assertAlmostEqual(result["vector_ms"], 8.0)
        self.assertAlmostEqual(result["keyword_ms"], 2.0)
        self.assertAlmostEqual(result["fusion_ms"], 0.5)
        self.assertAlmostEqual(result["ttft_ms"], 100.0)
        self.assertAlmostEqual(result["full_response_ms"], 300.0)
        self.assertAlmostEqual(result["first_status_ms"], 20.0)
        self.assertEqual(
            {key: result[key] for key in ("draft_ms", "check_ms", "conflict_ms", "answer_ms", "drafts", "check_calls")},
            {"draft_ms": 150.0, "check_ms": 90.0, "conflict_ms": 40.0, "answer_ms": 285.0, "drafts": 1, "check_calls": 3},
        )
        self.assertEqual(
            {key: result[key] for key in ("draft_ms", "check_ms", "conflict_ms", "answer_ms", "drafts", "check_calls")},
            {"draft_ms": 150.0, "check_ms": 90.0, "conflict_ms": 40.0, "answer_ms": 285.0, "drafts": 1, "check_calls": 3},
        )


if __name__ == "__main__":
    unittest.main()
