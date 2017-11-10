from unittest import TestCase

import zoe

class IntentsTest(TestCase):
    def test_no_inner(self):
        intent = {
            'intent': 'test'
        }
        chosen, _ = zoe.IntentTools.lookup(intent)
        self.assertIs(intent, chosen)

    def test_one_inner(self):
        intent = {
            'intent': 'test',
            'a': {
                'intent': 'a'
            }
        }
        chosen, _ = zoe.IntentTools.lookup(intent)
        self.assertIs(intent['a'], chosen)

    def test_inner_order(self):
        intent = {
            'intent': 'test',
            'a': {
                'intent': 'a'
            },
            'z': {
                'intent': 'z'
            }
        }
        chosen, _ = zoe.IntentTools.lookup(intent)
        self.assertIs(intent['a'], chosen)

    def test_chain(self):
        intent = {
            'intent': 'test',
            'a': {
                'intent': 'a',
                'b': {
                    'intent': 'b',
                    'c': {
                        'intent': 'c'
                    }
                }
            },
        }
        chosen, _ = zoe.IntentTools.lookup(intent)
        self.assertIs(intent['a']['b']['c'], chosen)

    def test_array(self):
        intent = {
            'intent': 'test',
            'a': [
                {
                    'intent': 'b'
                },
                {
                    'intent': 'c'
                },
            ],
        }
        chosen, _ = zoe.IntentTools.lookup(intent)
        self.assertIs(intent['a'][0], chosen)

    def test_quote(self):
        intent = {
            'a!': {
                'intent': 'a'
            },
            'b': {
                'intent': 'b'
            }
        }
        chosen, _ = zoe.IntentTools.lookup(intent)
        self.assertIs(intent['b'], chosen)

    def test_parent1(self):
        intent = {
            'a': {
                'intent': 'a',
                'params': {
                    'intent': 'b'
                }
            }
        }
        _, parent = zoe.IntentTools.lookup(intent)
        self.assertIs(intent['a'], parent)

    def test_parent2(self):
        intent = {
            'a': {
                'intent': 'a',
                'params': {
                    'intent': 'b',
                    'params': {
                        'intent': 'c'
                    }
                }
            }
        }
        _, parent = zoe.IntentTools.lookup(intent)
        self.assertIs(intent['a']['params'], parent)

    def test_match_basic(self):
        self.assertIs(True, zoe.IntentTools.matches(1, 1))
        self.assertIs(False, zoe.IntentTools.matches(1, 2))
        self.assertIs(True, zoe.IntentTools.matches("a", "a"))
        self.assertIs(False, zoe.IntentTools.matches("a", "b"))
        self.assertIs(False, zoe.IntentTools.matches(1, "b"))
        self.assertIs(True, zoe.IntentTools.matches("*", "b"))
        self.assertIs(True, zoe.IntentTools.matches("*", 1))
        self.assertIs(True, zoe.IntentTools.matches("*", {'a': 4}))

    def test_match_dict(self):
        left = { 'a': 1 }
        right = { 'a': 1 }
        self.assertIs(True, zoe.IntentTools.matches(left, right))
        left = { 'a': {'b': 'c'} }
        right = { 'a': {'b': 'c'} }
        self.assertIs(True, zoe.IntentTools.matches(left, right))
        left = { 'a': {'b': 'c'} }
        right = { 'a': {'b': 'd'} }
        self.assertIs(False, zoe.IntentTools.matches(left, right))

    def test_match_types(self):
        self.assertIs(True, zoe.IntentTools.matches(str, 'a'))
        self.assertIs(True, zoe.IntentTools.matches({'a': {'b': str}}, {'a': {'b': 'c'}}))
