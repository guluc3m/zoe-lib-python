from unittest import TestCase

import zoe


class PatternMatchTest(TestCase):

    def test_match_basic(self):
        self.assertTrue(zoe.IntentTools.matches(1, 1))
        self.assertFalse(zoe.IntentTools.matches(1, 2))
        self.assertTrue(zoe.IntentTools.matches("a", "a"))
        self.assertFalse(zoe.IntentTools.matches("a", "b"))
        self.assertFalse(zoe.IntentTools.matches(1, "b"))
        self.assertTrue(zoe.IntentTools.matches("*", "b"))
        self.assertTrue(zoe.IntentTools.matches("*", 1))
        self.assertTrue(zoe.IntentTools.matches("*", {'a': 4}))

    def test_match_dict(self):
        left = {'a': 1}
        right = {'a': 1}
        self.assertIs(True, zoe.IntentTools.matches(left, right))
        left = {'a': {'b': 'c'}}
        right = {'a': {'b': 'c'}}
        self.assertIs(True, zoe.IntentTools.matches(left, right))
        left = {'a': {'b': 'c'}}
        right = {'a': {'b': 'd'}}
        self.assertIs(False, zoe.IntentTools.matches(left, right))

    def test_match_types(self):
        self.assertTrue(zoe.IntentTools.matches(str, 'a'))
        self.assertTrue( zoe.IntentTools.matches({'a': {'b': str}}, {'a': {'b': 'c'}}))
