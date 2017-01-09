# -*- coding: utf-8 -*-
#
# This file is part of Zoe Assistant
# Licensed under MIT license - see LICENSE file
#

import logging
import pika
import json
import sys
import os

url = os.environ.get('RABBITMQ_URL')
logging.getLogger("pika").setLevel(logging.WARNING)

class RabbitMQClient:
    QUEUE = 'zoemessages'
    ROUTING_KEY = 'zoemessages'
    EXCHANGE = 'zoeexchange'

    def __init__(self, url, handler):
        self._url = url
        self._handler = handler

    def run(self):
        params = pika.URLParameters(self._url)
        params.socket_timeout = 5
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._channel.exchange_declare(exchange = self.EXCHANGE, type = 'fanout')

        result = self._channel.queue_declare(exclusive = True)
        self._queue_name = result.method.queue
        self._channel.queue_bind(exchange = self.EXCHANGE, queue = self._queue_name)

        self._channel.basic_consume(self._handler, queue = self._queue_name, no_ack = True)
        self._channel.start_consuming()

    def send(self, msg):
        if not self._channel:
            return
        if isinstance(msg, dict):
            msg = json.dumps(msg)
        elif not isinstance(msg, str):
            msg = str(msg)
        self._channel.basic_publish(exchange = self.EXCHANGE, routing_key = self.ROUTING_KEY, body = msg)

class IntentTools:
    def lookup(intent):
        """ finds the innermost intent to solve.
            Traverses the intent tree, accumulating all objects,
            and returns the first one that is actually an intent.
            Yes, this can be optimized, but who cares.
        """
        a = []
        def traverse(intent, acc, trycatch = None):
            if 'try' in intent:
                traverse(intent['try'], acc, intent)
            else:
                keys = sorted(intent)
                for key in keys:
                    value = intent[key]
                    if isinstance(value, dict):
                        traverse(value, acc, trycatch)
                    elif isinstance(value, list):
                        for p in value:
                            traverse(p, acc, trycatch)
            acc.append((intent, trycatch))
        traverse(intent, a)
        for (i, t) in a:
            if 'intent' in i or 'try' in i:
                return (i, t)

    def inner_intent(intent):
        chosen, trycatch = IntentTools.lookup(intent)
        return chosen

    def substitute(old, new):
        """ replaces a dict's contents with the ones in another dict """
        old.clear()
        old.update(new)

class DecoratedAgent:
    def __init__(self, name, agent, listener = None):
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
            self._listener = RabbitMQClient(url, self.incoming)
        agent.send = self._listener.send
        self._listener.run()

    def incoming(self, ch, method, properties, body):
        incoming = json.loads(body.decode('utf-8'))
        if (len(incoming) == 0):
            return
        result, error = self.dispatch(incoming)
        if not result:
            return
        self._listener.send(json.dumps(result))

    def dispatch(self, original):
        incoming = dict(original)
        intent, method = self.find_method(incoming)
        if not method:
            return None, 'ignored'
        result = method(intent)
        if not result:
            return None, 'consumed'
        IntentTools.substitute(intent, result)
        return incoming, None

    def find_method(self, incoming):
        methods = []
        for method in self._candidates:
            selector = IntentDecorations.get_selector(method)
            filt = IntentDecorations.get_filter(method)
            result = selector(incoming)
            if not filt(result):
                return None, None
            if result and len(result) > 0:
                methods.append(method)
            if len(methods) == 0:
                return None, None
            if len(methods) > 1:
                print('Too many methods')
                return None, None
        return result, methods[0]


class IntentDecorations:
    ATTR_SELECTOR = '__zoe__intent__selector__'
    ATTR_FILTER = '__zoe__intent__filter__'
    def set_selector(f, selector):
        setattr(f, IntentDecorations.ATTR_SELECTOR, selector)

    def get_selector(method):
        if hasattr(method, IntentDecorations.ATTR_SELECTOR):
            return getattr(method, IntentDecorations.ATTR_SELECTOR)
        else:
            return Inner.SELECTOR

    def set_filter(f, filter):
        setattr(f, IntentDecorations.ATTR_FILTER, filter)

    def get_filter(method):
        return getattr(method, IntentDecorations.ATTR_FILTER)


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
        IntentDecorations.set_filter(f, self._lam)
        return f

class Inner(Selector):
    SELECTOR = lambda intent: IntentTools.inner_intent(intent)
    def __init__(self):
        Selector.__init__(self, Inner.SELECTOR)

class Raw(Selector):
    SELECTOR = lambda intent: intent
    def __init__(self):
        Selector.__init__(self, Raw.SELECTOR)

class Intent(Filter):
    def __init__(self, name):
        Filter.__init__(self, lambda intent: intent['intent'] == name)

class Any(Filter):
    MAPPING = lambda intent: True
    def __init__(self):
        Filter.__init__(self, Any.MAPPING)

class Agent:
    def __init__(self, name):
        self._name = name

    def __call__(self, i):
        DecoratedAgent(self._name, i())
