"""Separate metric-review regression; oracle fixtures are not model answers."""
import unittest
import memory_task_contract as contract
from test_memory_tasks import fixture


class Metrics(unittest.TestCase):
    def test_correct_abstention_is_not_task_resolution(self):
        with_context = contract.score(*fixture('with-context'))
        without_context = contract.score(*fixture('without-context'))
        self.assertEqual(with_context['accuracy'], without_context['accuracy'])
        self.assertEqual(with_context['accuracy_metric'], 'packet_grounded_response')
        self.assertEqual(with_context['answerable_resolution'], {'total': 25, 'resolved': 25, 'rate': 1.0})
        self.assertEqual(without_context['answerable_resolution'], {'total': 25, 'resolved': 0, 'rate': 0.0})


if __name__ == '__main__':
    unittest.main(verbosity=2)
