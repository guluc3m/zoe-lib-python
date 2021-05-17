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
import re

""" Contains the reference implementation of the Zoe language
and some tools to implement agents.


Running an agent
----------------

This implementation is based in decorators. An agent is written like:

    @Agent('Whatever')
    class MyAgent:
        ...

The @Agent decorator connects to the bus and waits for incoming messages.


Dispatching intents
-------------------

In order to implement an intent, define a method decorated with @Intent:

    @Agent('Whatever')
    class MyAgent:

        @Intent('sayHello')
        def something(self, intent):
            ...

When the agent is launched and an intent with that name has to be dispatched,
this method is invoked. If it does not return anything, the intent is assumed to
have been consumed. If it returns something, it is considered as the intent
response:

    @Agent('Whatever')
    class MyAgent:

        @Intent('sayHello')
        def something(self, intent):
            return {'data':'string', 'value': 'Hello!'}

Intent data can be automatically injected as parameters with the @Inject decorator:

    @Agent('Whatever')
    class MyAgent:

        @Intent('sayHello')
        @Inject()
        def something(self, intent, name, age=30):
            # `intent` will contain the entire intent object
            # `name` will contain `intent['name']`
            # `age` will contain `intent['age']` or 30 if `intent['age']` is missing

A convenient way of validating incoming intents structure is using the @Match decorator:

    @Agent('Whatever')
    class MyAgent:

        @Match('sayHello', {'name': str, 'credentials': {'username', 'password'}})
        @Inject()
        def something(self, name, credentials, age=30):
            # The intent contains a `name` (with a str value) and `credentials` (with a dict value)
            # The `credentials` value contains a `username` and `password`, with unknown types

Refer to the `patternmatch` tests to learn more about patterns.

Instead of a specific intent, an agent can be interested in any message. In this
case, decorate the dispatcher with @Any.

    @Agent('Whatever')
    class MyAgent:

        @Any()
        def something(self, intent):
            # Will receive all intents.

If a dispatcher is decorated with @Raw, the entire intent tree is received. Use
with caution.

    @Agent('Whatever')
    class MyAgent:

        @Any()
        @Raw()
        def something(self, intent):
            # here, all root intents are captured

When an error occurs, the dispatcher method should return an error object:

    @Agent('Whatever')
    class MyAgent:

        @Intent('sayHello')
        def something(self, intent):
            return {'error': 'something-terrible-happened', ... }


Error handling
--------------

Errors are automatically propagated through the intent tree unless a dispatcher
is decorted with @Catch. In this case, if an intent receives an error from a
sub-intent, it will be explicitly handled by the dispatcher method:

    @Agent('Whatever')
    class MyAgent:

        @Intent('sayHello')
        @Catch()
        def something(self, intent):
            if 'error' in intent:
                # error handling
            else:
                return ...


NOTE: right now, errors are handled manually in the dispatcher. It would be
great to map exceptions to errors.

"""

bootstrap = os.environ.get('KAFKA_SERVERS')

class KafkaClient:
    """ A simple Kafka consumer/producer """

    TOPIC = 'zoe'
    """ All messages are sent to this topic.
    There is room for optimizations here, but let's keep it simple for now
    """

    def __init__(self, url, handler, group):
        """ Creates a client
        :param str url: The Kafka URL.
        :param handler: The incoming message handler function.
        :param str group: The consumer group name.
        """
        self._url = url
        self._handler = handler
        self._group = group

    def run(self):
        """ Starts consuming messages """
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
        """ Send a message to Kafka """
        if not self._producer:
            return
        if isinstance(msg, dict):
            msg = json.dumps(msg)
        elif not isinstance(msg, str):
            msg = str(msg)
        self._producer.send(KafkaClient.TOPIC, msg.encode('ascii'))


class IntentTools:
    """ Contains the intent resolution algorithm """

    def lookup(intent, parent=None):
        """ Finds the innermost leftmost intent to solve.
            Traverses the intent tree, returning the first
            one that is actually an intent and its parent intent.
        """
        if isinstance(intent, dict):
            keys = sorted(intent)
            for key in keys:
                if key[-1] == '!':
                    continue
                value = intent[key]
                res, par = IntentTools.lookup(value, intent if 'intent' in intent else parent)
                if res:
                    return res, par
            if 'intent' in keys:
                return intent, parent
        elif isinstance(intent, list):
            for value in intent:
                res, par = IntentTools.lookup(value, parent)
                if res:
                    return res, par
        return None, None

    def inner_intent(intent):
        """ Just an alias """
        return IntentTools.lookup(intent)

    def matches(pattern, value):
        """ Checks for structural matching between a value and a pattern.
        This is used for intent pattern matching. See the 'patternmatch' tests.
        """
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
        if hasattr(pattern, 'fullmatch'):
            return bool(pattern.fullmatch(value))
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
    """ The Agent decorator implementation.

    Methods in an agent are decorated with @Intent, @Raw, etc.
    There are three basic kinds of decorators: Selector, Filter and
    Invoker.

      - Selector: extracts an intent from an intent tree
      - Filter: decides if an intent should be analyzed
      - Invoker: invokes the dispatcher method
    """

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

    def run(self):
        self._listener.run()

    def incoming(self, body):
        """ Invoked when an incoming message arrives """
        try:
            incoming = json.loads(body)
            if (len(incoming) == 0):
                return
            result, error = self.dispatch(incoming)
            if not result:
                return
            self._listener.send(json.dumps(result))
        except:
            # print("Dropping message", body)
            pass

    def dispatch(self, original):
        """ Invokes a dispatcher method that fits the incoming intent,
        handling errors and outputs. """
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
        """ Finds a dispatcher method for an incoming intent """
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
    """ Helper methods to get/set selectors, filters, etc. """

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
    """ Decides which intent from an intent tree should be analyzed """

    def __init__(self, lam):
        self._lam = lam

    def __call__(self, f):
        IntentDecorations.set_selector(f, self._lam)
        return f


class Filter:
    """ Decides if an intent should be analyzed """

    def __init__(self, lam):
        self._lam = lam

    def __call__(self, f):
        IntentDecorations.add_filter(f, self._lam)
        return f


class Mark:
    """ Dispatcher metadata """

    def __init__(self, mark):
        self._mark = mark

    def __call__(self, f):
        IntentDecorations.add_mark(f, self._mark)
        return f


class Invoker:
    """ Implements the dispatcher invocation strategy. """

    def __init__(self, lam):
        self._lam = lam

    def __call__(self, f):
        IntentDecorations.set_invoker(f, self._lam)
        return f


class Analyze:
    """ A specific decorator for NLP analysis.

    This is work in progress...
    """

    def __init__(self, definition):
        self._regex = re.compile(definition)

    def invoke(method, intent, regex):
        matches = list(regex.fullmatch(intent['text']).groups())
        args, varargs, keywords, defaults = inspect.getargspec(method)
        args = args[1:]
        params = []
        for arg in args:
            if arg == "intent":
                param = intent
            else:
                try:
                    param = matches.pop(0)
                except:
                    raise Exception('Arguments and captures do not match!')
            params.append(param)
        return method(*params)

    def __call__(self, f):
        IntentDecorations.add_filter(f, lambda intent: IntentTools.matches({
            'intent': 'natural.analyze',
            'text': self._regex
        }, intent))
        IntentDecorations.set_invoker(f, lambda method, intent: Analyze.invoke(method, intent, self._regex))
        return f

    def intent(what):
        return {
            'intent': 'natural.analyze',
            'text': what
        }


class Inner(Selector):
    """ Selects the innermost leftmost intent.

    This is the default selector."""

    SELECTOR = lambda intent: IntentTools.lookup(intent)

    def __init__(self):
        Selector.__init__(self, Inner.SELECTOR)


class Raw(Selector):
    """ Selects the entire intent tree. """

    SELECTOR = lambda intent: (intent, None)

    def __init__(self):
        Selector.__init__(self, Raw.SELECTOR)


class Intent(Filter):
    """ Filters an intent with a given name. """

    def __init__(self, name):
        Filter.__init__(self, lambda intent: 'intent' in intent and
                                             intent['intent'] == name)


class Match(Filter):
    """ Filters an intent with a given name and structure. """

    def __init__(self, name, pattern):
        Filter.__init__(self, lambda intent: 'intent' in intent and
                                             intent['intent'] == name and
                                             IntentTools.matches(pattern, intent))


class SimpleInvoker(Invoker):
    """ Invokes a dispatcher passing the entire intent as the only parameter.

    This is the default invoker."""

    INVOKER = lambda method, intent: method(intent)

    def __init__(self):
        Invoker.__init__(self, SimpleInvoker.INVOKER)


class Inject(Invoker):
    """ Invokes a dispatcher mapping its arguments to intent values. """

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
    """ Filters all intents. """

    MAPPING = lambda intent: True

    def __init__(self):
        Filter.__init__(self, Any.MAPPING)


class Catch(Mark):
    """ Avoids automatic error handling. """

    MARK = 'Catch'

    def __init__(self):
        Mark.__init__(self, Catch.MARK)


class Agent:
    """ Decorates a class as a Zoe agent. """

    def __init__(self, name):
        self._name = name
        self.agent = DecoratedAgent(self._name, self)

    def __call__(self):
        self.agent.run()
