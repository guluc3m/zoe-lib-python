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

    def test_array2(self):
        intent = {
            'intent': 'test',
            'a': [['b'], ['c', 'd']]
        }
        chosen, _ = zoe.IntentTools.lookup(intent)
        self.assertIs(intent, chosen)

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
