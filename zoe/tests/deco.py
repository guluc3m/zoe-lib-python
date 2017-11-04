from unittest import TestCase

import zoe

class DecoTest(TestCase):

    class FakeListener:
        def run(self):
            pass
        def send(self, msg):
            self.msg = msg

    def _run(self, klass, incoming):
        listener = DecoTest.FakeListener()
        return zoe.DecoratedAgent('', klass(), listener = listener).dispatch(incoming)


    def test_inner(self):
        class TestAgent:
            @zoe.Intent('a')
            def xxx(self, intent):
                return {'data': 'ack'}
        incoming = {
            'intent': 'b',
            'params': {
                'intent': 'a'
            }
        }
        expected = {
            'intent': 'b',
            'params': {'data': 'ack'}
        }
        self.assertEqual(expected, self._run(TestAgent, incoming)[0])

    def test_outer(self):
        class TestAgent:
            @zoe.Intent('b')
            @zoe.Raw()
            def xxx(self, intent):
                return {'data': 'ack'}
        incoming = {
            'intent': 'b',
            'params': {
                'intent': 'a'
            }
        }
        expected = {
            'data': 'ack'
        }
        self.assertEqual(expected, self._run(TestAgent, incoming)[0])

    def test_all(self):
        class TestAgent:
            @zoe.Any()
            def xxx(self, intent):
                return {'data': 'ack'}
        incoming = {
            'intent': 'b',
            'params': {
                'intent': 'a'
            }
        }
        expected = {
            'intent': 'b',
            'params': {'data': 'ack'}
        }
        self.assertEqual(expected, self._run(TestAgent, incoming)[0])

    def test_all_outer(self):
        class TestAgent:
            @zoe.Any()
            @zoe.Raw()
            def xxx(self, intent):
                return {'data': 'ack'}
        incoming = {
            'intent': 'b',
            'params': {
                'intent': 'a'
            }
        }
        expected = {
            'data': 'ack'
        }
        self.assertEqual(expected, self._run(TestAgent, incoming)[0])

    def test_not_dispatched(self):
        class TestAgent:
            @zoe.Intent('a')
            def xxx(self, intent):
                return {'data': 'ack'}
        incoming = {
            'intent': 'a',
            'params': {
                'intent': 'c'
            }
        }
        expected = None, 'ignored'
        self.assertEqual(expected, self._run(TestAgent, incoming))

    def test_consumed(self):
        class TestAgent:
            @zoe.Intent('a')
            def xxx(self, intent):
                pass
        incoming = {
            'intent': 'b',
            'params': {
                'intent': 'a'
            }
        }
        expected = None, 'consumed'
        self.assertEqual(expected, self._run(TestAgent, incoming))

    def test_two_intents(self):
        class TestAgent:
            @zoe.Intent('a')
            def a(self, intent):
                return {'data': 'ack-a'}
            @zoe.Intent('b')
            def b(self, intent):
                return {'data': 'ack-b'}
        incoming = {
            'intent': 'c',
            'params': {
                'intent': 'a'
            }
        }
        expected = {
            'intent': 'c',
            'params': {'data': 'ack-a'}
        }
        self.assertEqual(expected, self._run(TestAgent, incoming)[0])

    def test_no_catch(self):
        class TestAgent:
            called = False
            @zoe.Intent('a')
            def a(self, intent):
                TestAgent.called = True
        # The agent has no catch, so the error is automatically returned
        incoming = {
            'intent': 'a',
            'error': 'error'
        }
        self._run(TestAgent, incoming)
        self.assertFalse(TestAgent.called)

    def test_catch(self):
        class TestAgent:
            called = False
            @zoe.Intent('a')
            @zoe.Catch()
            def a(self, intent):
                TestAgent.called = True
        # The agent has @Catch, so the error is not automatically returned
        incoming = {
            'intent': 'a',
            'error': 'error'
        }
        self._run(TestAgent, incoming)
        self.assertTrue(TestAgent.called)

    def test_transform_trycatch(self):
        class TestAgent:
            @zoe.Intent('a')
            def a(self, intent):
                return { 'error': 'error' }
            @zoe.Intent('b')
            def b(self, intent):
                return { 'data': 'ok' }
            @zoe.Intent('try')
            @zoe.Catch()
            def tr(self, intent):
                if 'error' in intent['try']:
                    return intent['catch!']
                else:
                    return intent['try']
        incoming = {
            'intent': 'try',
            'try': {
                'intent': 'a'
            },
            'catch!': {
                'intent': 'b'
            }
        }
        expected1 = {
            'intent': 'try',
            'error': 'error',
            'try': {
                'error': 'error'
            },
            'catch!': {
                'intent': 'b'
            }
        }
        expected2 = {
            'intent': 'b'
        }
        self.assertEqual(expected1, self._run(TestAgent, incoming)[0])
        self.assertEqual(expected2, self._run(TestAgent, expected1)[0])

    def test_error_in_parent(self):
        class TestAgent:
            @zoe.Intent('b')
            def b(self, intent):
                return { 'blah': 'bleh' }
            @zoe.Intent('c')
            def c(self, intent):
                return { 'error': 'error' }
        incoming = {
            'intent': 'a',
            'param': {
                'intent': 'b',
                'param': {
                    'intent': 'c',
                    'param': 'blah'
                }
            }
        }
        expected1 = {
            'intent': 'a',
            'param': {
                'intent': 'b',
                'param': {
                    'error': 'error'
                },
                'error': 'error'
            }
        }
        expected2 = {
            'intent': 'a',
            'param': {
                'error': 'error'
            },
            'error': 'error'
        }
        self.assertEqual(expected1, self._run(TestAgent, incoming)[0])
        self.assertEqual(expected2, self._run(TestAgent, expected1)[0])
