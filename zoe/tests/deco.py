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
        return zoe.DecoratedAgent('', klass(), listener=listener).dispatch(incoming)

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
                return {'error': 'error'}

            @zoe.Intent('b')
            def b(self, intent):
                return {'data': 'ok'}

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
                return {'blah': 'bleh'}

            @zoe.Intent('c')
            def c(self, intent):
                return {'error': 'error'}
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

    def test_match(self):
        class TestAgent:
            @zoe.Match('a', {'param1': str, 'param2': int, 'param3': {'a', 'b'}})
            def a(self, intent):
                return {
                    'ret': "%s %d %d %d" % (intent['param1'],
                                            intent['param2'],
                                            intent['param3']['a'],
                                            intent['param3']['b'])
                }
        incoming = {
            'intent': 'a',
            'param1': 'blah',
            'param2': 123,
            'param3': {
                'a': 8,
                'b': 9
            }
        }
        expected = {
            'ret': 'blah 123 8 9'
        }
        self.assertEqual(expected, self._run(TestAgent, incoming)[0])

    def test_invoker_inject(self):
        class TestAgent:
            @zoe.Any()
            @zoe.Inject()
            def a(self, intent, param1, param2=18):
                TestAgent.PARAM1 = param1
                TestAgent.PARAM2 = param2
        incoming = {
            'intent': 'a',
            'param1': 'blah',
            'param2': 123
        }
        self._run(TestAgent, incoming)[0]
        self.assertEqual('blah', TestAgent.PARAM1)
        self.assertEqual(123, TestAgent.PARAM2)

    def test_invoker_inject_defauls(self):
        class TestAgent:
            @zoe.Any()
            @zoe.Inject()
            def a(self, intent, param1, param2=18):
                TestAgent.PARAM1 = param1
                TestAgent.PARAM2 = param2
        incoming = {
            'intent': 'a',
            'param1': 'blah'
        }
        self._run(TestAgent, incoming)[0]
        self.assertEqual('blah', TestAgent.PARAM1)
        self.assertEqual(18, TestAgent.PARAM2)

    def test_match_and_inject(self):
        # nothing new, just a use case
        class TestAgent:
            @zoe.Inject()
            @zoe.Match('a', {'param1': str, 'param2': {'x', 'y'}})
            def a(self, intent, param1, param2):
                TestAgent.PARAM1 = param1
                TestAgent.PARAM2 = param2['x'] + param2['y']
        incoming = {
            'intent': 'a',
            'param1': 'bleh',
            'param2': {
                'x': 9,
                'y': 8
            }
        }
        self._run(TestAgent, incoming)[0]
        self.assertEqual('bleh', TestAgent.PARAM1)
        self.assertEqual(17, TestAgent.PARAM2)

    def test_multiple_intents_per_method(self):
        class TestAgent:
            @zoe.Intent('a')
            @zoe.Intent('b')
            def a(self, intent):
                return {'data': 'ack'}
        incoming = {
            'intent': 'b',
            'params': {
                'intent': 'a'
            }
        }
        expected1 = {
            'intent': 'b',
            'params': {'data': 'ack'}
        }
        expected2 = {
            'data': 'ack'
        }
        self.assertEqual(expected1, self._run(TestAgent, incoming)[0])
        self.assertEqual(expected2, self._run(TestAgent, expected1)[0])

    def test_analyzer(self):
        class TestAgent:
            @zoe.Analyze('hello, ([a-z]+)')
            def a(self, intent, world):
                return {'data': world}
        incoming = {
            'intent': 'natural.analyze',
            'text': 'hello, world'
        }
        expected = {'data': 'world'}
        self.assertEqual(expected, self._run(TestAgent, incoming)[0])

    def test_analyzer_2(self):
        class TestAgent:
            @zoe.Analyze('action<send> (objective<.+>) .* (object<.*>)')
            def send(self, destination, what):
                return {
                    'intent': 'email.send',
                    'recipient': zoe.Analyze.intent(destination),
                    'payload': zoe.Analyze.intent(what)
                }

            @zoe.Analyze('objective<(.+)>')
            def objective(self, name):
                return {
                    'data': 'user',
                    'name': name,
                    'email': '%s@%s.com' % (name.lower(), name.lower())
                }

            @zoe.Analyze('object<email saying (.+)>')
            def email(self, content):
                return {
                    'data': 'email',
                    'content': content
                }

        incoming = {
            'intent': 'natural.analyze',
            'text': 'action<send> objective<David> an object<email saying hello>'
        }
        expected1 = {
            'intent': 'email.send',
            'recipient': {
                'intent': 'natural.analyze',
                'text': 'objective<David>'
            },
            'payload': {
                'intent': 'natural.analyze',
                'text': 'object<email saying hello>'
            }
        }
        expected2 = {
            'intent': 'email.send',
            'recipient': {
                'intent': 'natural.analyze',
                'text': 'objective<David>'
            },
            'payload': {
                'data': 'email',
                'content': 'hello'
            }
        }
        expected3 = {
            'intent': 'email.send',
            'recipient': {
                'data': 'user',
                'name': 'David',
                'email': 'david@david.com'
            },
            'payload': {
                'data': 'email',
                'content': 'hello'
            }
        }
        self.assertEqual(expected1, self._run(TestAgent, incoming)[0])
        self.assertEqual(expected2, self._run(TestAgent, expected1)[0])
        self.assertEqual(expected3, self._run(TestAgent, expected2)[0])
