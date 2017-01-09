from unittest import TestCase

import zoe

class IntentsTest(TestCase):
    def test_no_inner(self):
        intent = {
            'intent': 'test'
        }
        chosen = zoe.IntentTools.inner_intent(intent)
        self.assertIs(intent, chosen)

    def test_one_inner(self):
        intent = {
            'intent': 'test',
            'a': {
                'intent': 'a'
            }
        }
        chosen = zoe.IntentTools.inner_intent(intent)
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
        chosen = zoe.IntentTools.inner_intent(intent)
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
        chosen = zoe.IntentTools.inner_intent(intent)
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
        chosen = zoe.IntentTools.inner_intent(intent)
        self.assertIs(intent['a'][0], chosen)

    def test_trycatch_1(self):
        intent = {
            'try': {
                'intent': 'a'
            },
            'catch': {
                'intent': 'b'
            }
        }
        chosen, trycatch = zoe.IntentTools.lookup(intent)
        self.assertIs(intent['try'], chosen)
        self.assertIs(intent, trycatch)

    def test_trycatch_2(self):
        intent = {
            'try': {
                'try': {
                    'intent': 'a'
                },
                'catch': {
                    'intent': 'b'
                }
            },
            'catch': {
                'intent': 'b'
            }
        }
        chosen, trycatch = zoe.IntentTools.lookup(intent)
        self.assertIs(intent['try']['try'], chosen)
        self.assertIs(intent['try'], trycatch)

    def test_trycatch_3(self):
        intent = {
            'try': {
                'try': {
                    'data': 'ok'
                },
                'catch': {
                    'data': 'ko'
                }
            },
            'catch': {
                'intent': 'b'
            }
        }
        chosen, trycatch = zoe.IntentTools.lookup(intent)
        self.assertIs(intent['try'], chosen)
