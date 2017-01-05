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
logging.basicConfig(level = logging.INFO)

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
        if self._channel:
            self._channel.basic_publish(exchange = self.EXCHANGE, routing_key = self.ROUTING_KEY, body = msg)


class DecoratedAgent:
    def __init__(self, name, agent):
        self._name = name
        self._agent = agent
        self._logger = logging.getLogger(name)
        self._candidates = []
        for m in dir(agent):
            k = getattr(agent, m)
            if hasattr(k, "__zoe__intent__"):
                self._candidates.append(k)
            if hasattr(k, "__zoe__intent__any__"):
                self._candidates.append(k)
        self._listener = RabbitMQClient(url, self.incoming)
        agent.send = self._listener.send
        self._listener.run()

    def sendbus(self, json):
        self._listener.send(json)

    def substitute(self, old, new):
        """ replaces a dict's contents with the ones in another dict """
        old.clear()
        old.update(new)

    def tojson(self, dic):
        """ guess what """
        return json.dumps(dic)

    def fromjson(self, st):
        """ guess what """
        return json.loads(st)

    def innerintent(self, intent):
        """ finds the innermost intent to solve.
            Traverses the intent tree, accumulating all objects,
            and returns the first one that is actually an intent.
            Yes, this can be optimized, but who cares.
        """
        a = []
        def traverse(intent, acc):
            if 'payloads' in intent:
                for p in intent['payloads']:
                    traverse(p, acc)
            acc.append(intent)
        traverse(intent, a)
        for i in a:
            if 'intent' in i:
                return i

    def incoming(self, ch, method, properties, body):
        incoming = self.fromjson(body.decode('utf-8'))
        if (len(incoming) == 0):
            return
        inner = self.innerintent(incoming)
        intentName = inner['intent']
        chosen = None
        for c in self._candidates:
            if hasattr(c, '__zoe__intent__') and c.__zoe__intent__ == intentName:
                chosen = c
                break
            if hasattr(c, '__zoe__intent__any__'):
                chosen = c
                break
        if not chosen:
            return
        ret = chosen(inner)
        if not ret:
            return
        self.substitute(inner, ret)
        self.sendbus(self.tojson(incoming))

class Intent:
    def __init__(self, name):
        self._name = name

    def __call__(self, f):
        setattr(f, '__zoe__intent__', self._name)
        return f

class Any:
    def __init__(self):
        pass

    def __call__(self, f):
        setattr(f, '__zoe__intent__any__', True)
        return f

class Agent:
    def __init__(self, name):
        self._name = name

    def __call__(self, i):
        DecoratedAgent(self._name, i())
