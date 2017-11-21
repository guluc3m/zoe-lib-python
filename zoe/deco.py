# -*- coding: utf-8 -*-
#
# This file is part of Zoe Assistant
# Licensed under MIT license - see LICENSE file
#

import inspect
import logging
import kafka
import json
import sys
import os

bootstrap = os.environ.get('KAFKA_SERVERS')


class KafkaClient:
    TOPIC = 'zoe'

    def __init__(self, url, handler, group):
        self._url = url
        self._handler = handler
        self._group = group

    def run(self):
        print("Running!")
        consumer = kafka.KafkaConsumer(KafkaClient.TOPIC,
                                       bootstrap_servers=bootstrap,
                                       group_id=self._group,
                                       enable_auto_commit=False)
        self._producer = kafka.KafkaProducer(bootstrap_servers=bootstrap)
        for message in consumer:
            self._handler(message.value.decode('utf-8'))
            consumer.commit()
        print("ended!")

    def send(self, msg):
        if not self._producer:
            return
        if isinstance(msg, dict):
            msg = json.dumps(msg)
        elif not isinstance(msg, str):
            msg = str(msg)
        self._producer.send(KafkaClient.TOPIC, msg.encode('ascii'))


class IntentTools:
    def lookup(intent, parent=None):
        """ finds the innermost leftmost intent to solve.
            Traverses the intent tree, accumulating all objects,
            and returns the first one that is actually an intent.
        """
        keys = sorted(intent)
        for key in keys:
            if key[-1] == '!':
                continue
            value = intent[key]
            if isinstance(value, dict):
                res, par = IntentTools.lookup(value, intent)
                if res:
                    return res, par
            elif isinstance(value, list):
                for p in value:
                    res, par = IntentTools.lookup(p, intent)
                    if res:
                        return res, par
        if 'intent' in keys:
            return intent, parent
        return None, None

    def inner_intent(intent):
        return IntentTools.lookup(intent)

    def matches(pattern, value):
        def matchSet(pattern, value):
            for k in pattern:
                if k not in value:
                    return False
            return True

        def matchDict(pattern, value):
            kl = sorted(pattern)
            kr = sorted(value)
            for l in kl:
                if l not in kr:
                    return False
                vl = pattern[l]
                vr = value[l]
                if not IntentTools.matches(vl, vr):
                    return False
            return True

        if pattern == "*":
            return True
        if pattern.__class__ == set and value.__class__ == dict:
            return matchSet(pattern, value)
        if pattern.__class__ == type:
            return isinstance(value, pattern)
        if pattern.__class__ != value.__class__:
            return False
        if pattern.__class__ == dict:
            return matchDict(pattern, value)
        return pattern == value

    def substitute(old, new):
        """ replaces a dict's contents with the ones in another dict """
        old.clear()
        old.update(new)


class DecoratedAgent:
    def __init__(self, name, agent, listener=None):
        self._name = name
        self._agent = agent
        self._logger = logging.getLogger(name)
        self._candidates = []
        for m in dir(agent):
            k = getattr(agent, m)
            if hasattr(k, IntentDecorations.ATTR_FILTER):
                self._candidates.append(k)
        if (listener):
            self._listener = listener
        else:
            self._listener = KafkaClient(bootstrap, self.incoming, name)
        agent.send = self._listener.send
        self._listener.run()

    def incoming(self, body):
        try:
            incoming = json.loads(body)
            if (len(incoming) == 0):
                return
            result, error = self.dispatch(incoming)
            if not result:
                return
            self._listener.send(json.dumps(result))
        except:
            print("Dropping message", body)
            pass

    def dispatch(self, original):
        incoming = dict(original)
        intent, parent, method = self.find_method(incoming)
        if not method:
            return None, 'ignored'
        if not IntentDecorations.is_marked(method, Catch.MARK):
            if 'error' in intent:
                IntentTools.substitute(intent, {'error': intent['error']})
                if parent is not None:
                    parent['error'] = intent['error']
                return incoming, 'error'
        invoker = IntentDecorations.get_invoker(method)
        result = invoker(method, intent)
        if not result:
            return None, 'consumed'
        IntentTools.substitute(intent, result)
        if 'error' in result:
            parent['error'] = result['error']
        return incoming, 'replaced'

    def find_method(self, incoming):
        methods = []
        for method in self._candidates:
            selector = IntentDecorations.get_selector(method)
            filts = IntentDecorations.get_filters(method)
            result, parent = selector(incoming)
            for filt in filts:
                if filt(result):
                    methods.append(method)
        if len(methods) == 0:
            return None, None, None
        if len(methods) > 1:
            print('Too many methods')
            return None, None, None
        return result, parent, methods[0]


class IntentDecorations:
    ATTR_SELECTOR = '__zoe__intent__selector__'
    ATTR_FILTER = '__zoe__intent__filter__'
    ATTR_MARKS = '__zoe__intent__marks__'
    ATTR_INVOKER = '__zoe__intent__invoker__'

    def set_selector(f, selector):
        setattr(f, IntentDecorations.ATTR_SELECTOR, selector)

    def get_selector(method):
        if hasattr(method, IntentDecorations.ATTR_SELECTOR):
            return getattr(method, IntentDecorations.ATTR_SELECTOR)
        else:
            return Inner.SELECTOR

    def add_filter(f, filt):
        if not hasattr(f, IntentDecorations.ATTR_FILTER):
            setattr(f, IntentDecorations.ATTR_FILTER, [])
        getattr(f, IntentDecorations.ATTR_FILTER).append(filt)

    def get_filters(method):
        return getattr(method, IntentDecorations.ATTR_FILTER)

    def add_mark(f, transform):
        if not hasattr(f, IntentDecorations.ATTR_MARKS):
            setattr(f, IntentDecorations.ATTR_MARKS, [])
        getattr(f, IntentDecorations.ATTR_MARKS).append(transform)

    def get_marks(method):
        if not hasattr(method, IntentDecorations.ATTR_MARKS):
            return []
        return getattr(method, IntentDecorations.ATTR_MARKS)

    def is_marked(method, mark):
        marks = IntentDecorations.get_marks(method)
        return mark in marks

    def set_invoker(f, invoker):
        setattr(f, IntentDecorations.ATTR_INVOKER, invoker)

    def get_invoker(method):
        if hasattr(method, IntentDecorations.ATTR_INVOKER):
            return getattr(method, IntentDecorations.ATTR_INVOKER)
        else:
            return SimpleInvoker.INVOKER


class Selector:
    def __init__(self, lam):
        self._lam = lam

    def __call__(self, f):
        IntentDecorations.set_selector(f, self._lam)
        return f


class Filter:
    def __init__(self, lam):
        self._lam = lam

    def __call__(self, f):
        IntentDecorations.add_filter(f, self._lam)
        return f


class Mark:
    def __init__(self, mark):
        self._mark = mark

    def __call__(self, f):
        IntentDecorations.add_mark(f, self._mark)
        return f


class Invoker:
    def __init__(self, lam):
        self._lam = lam

    def __call__(self, f):
        IntentDecorations.set_invoker(f, self._lam)
        return f


class Inner(Selector):
    def SELECTOR(intent):
        return IntentTools.lookup(intent)

    def __init__(self):
        Selector.__init__(self, Inner.SELECTOR)


class Raw(Selector):
    def SELECTOR(intent):
        return (intent, None)

    def __init__(self):
        Selector.__init__(self, Raw.SELECTOR)


class Intent(Filter):
    def __init__(self, name):
        Filter.__init__(self, lambda intent: 'intent' in intent and intent['intent'] == name)


class Match(Filter):
    def __init__(self, name, pattern):
        Filter.__init__(self, lambda intent: 'intent' in intent and intent['intent'] == name and IntentTools.matches(pattern, intent))


class SimpleInvoker(Invoker):
    INVOKER = lambda method, intent: method(intent)

    def __init__(self):
        Invoker.__init__(self, SimpleInvoker.INVOKER)


class Inject(Invoker):
    INVOKER = lambda method, intent: Inject.invoke(method, intent)

    def invoke(method, intent):
        args, varargs, keywords, defaults = inspect.getargspec(method)
        if defaults:
            defaults = dict(zip(reversed(args), reversed(defaults)))  # taken from http://stackoverflow.com/questions/12627118/get-a-function-arguments-default-value
        if defaults is None:
            defaults = {}
        args = args[1:]
        params = []
        for arg in args:
            if arg == "intent":
                param = intent
            elif arg in intent:
                param = intent[arg]
            elif arg in defaults:
                param = defaults[arg]
            else:
                param = None
            params.append(param)
        return method(*params)

    def __init__(self):
        Invoker.__init__(self, Inject.INVOKER)


class Any(Filter):
    MAPPING = lambda intent: True

    def __init__(self):
        Filter.__init__(self, Any.MAPPING)


class Catch(Mark):
    MARK = 'Catch'

    def __init__(self):
        Mark.__init__(self, Catch.MARK)


class Agent:
    def __init__(self, name):
        self._name = name

    def __call__(self, i):
        DecoratedAgent(self._name, i())
