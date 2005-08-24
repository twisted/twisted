from twisted.trial.unittest import TestCase, TestResult

class TestTestResult(TestCase):

    def test_shouldStop_is_false(self):
        self.assertEqual(TestResult().shouldStop, False)
