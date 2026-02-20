.. py:currentmodule:: rule_engine

Async Support
=============
Rule Engine includes a parallel async API that allows symbol resolvers and callables to perform
asynchronous I/O (database lookups, HTTP requests, etc.) without blocking the event loop. The
async API mirrors the synchronous one exactly — there are no changes to the existing sync methods.

.. versionadded:: 4.6.0

Why Async?
----------
The default synchronous API runs on a single thread. If a resolver needs to do I/O (e.g. look up a
value in a database), it must block that thread. In an async application this would stall the entire
event loop.

The async API solves this by:

* Allowing the ``resolver`` passed to :py:class:`~engine.Context` to be a coroutine function
  (``async def``).
* Allowing callables that appear in rule expressions to be coroutine functions.
* Isolating per-evaluation state (regex groups, comprehension variable scopes) per asyncio
  ``Task`` via :py:mod:`contextvars`, so concurrent evaluations never interfere with each other.

New Methods
-----------
Three new methods are added to :py:class:`~engine.Rule`. They are all coroutines and must be
``await``\ed (or passed to :py:func:`asyncio.run`):

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Method
     - Description
   * - ``await rule.evaluate_async(thing)``
     - Evaluates the rule against *thing*, returning the raw result value (same semantics as
       :py:meth:`~engine.Rule.evaluate`).
   * - ``await rule.matches_async(thing)``
     - Returns ``True``/``False`` (same semantics as :py:meth:`~engine.Rule.matches`).
   * - ``async for x in rule.filter_async(things)``
     - Async generator that yields items from *things* for which the rule matches (same semantics
       as :py:meth:`~engine.Rule.filter`).

Basic Usage
-----------
Async evaluation with a synchronous resolver works without any changes to the context:

.. code-block:: python

   import asyncio
   import rule_engine

   rule = rule_engine.Rule('age > 18')

   async def main():
       print(await rule.matches_async({'age': 25}))  # True
       print(await rule.matches_async({'age': 10}))  # False

   asyncio.run(main())

Async Resolver
--------------
Pass an ``async def`` function as the *resolver* argument to :py:class:`~engine.Context`. The
resolver must still follow the standard signature ``resolver(thing, name)`` and raise
:py:class:`~errors.SymbolResolutionError` on failure — it may simply be declared with ``async def``
instead of ``def``.

.. code-block:: python

   import asyncio
   import rule_engine

   async def db_resolver(thing, name):
       # simulate async I/O (e.g. an ORM query or Redis lookup)
       await asyncio.sleep(0)
       return thing[name]

   context = rule_engine.Context(resolver=db_resolver)
   rule = rule_engine.Rule('status == "active" and score >= 50', context=context)

   async def main():
       record = {'status': 'active', 'score': 75}
       print(await rule.matches_async(record))  # True

   asyncio.run(main())

.. note::
   A sync resolver also works with :py:meth:`~engine.Rule.evaluate_async`. You only need an async
   resolver if the symbol lookup itself is inherently asynchronous.

Async Callable in an Expression
--------------------------------
Callables referenced inside a rule expression may also be coroutine functions. The engine
automatically ``await``\s any callable that returns an awaitable when
:py:meth:`~engine.Rule.evaluate_async` is used.

.. code-block:: python

   import asyncio
   import decimal
   import types
   import rule_engine

   async def fetch_score(user_id):
       # imagine this hits a remote API
       await asyncio.sleep(0)
       return decimal.Decimal('95')

   context = rule_engine.Context(resolver=rule_engine.resolve_attribute)
   rule = rule_engine.Rule('get_score(user_id) >= 90', context=context)

   async def main():
       thing = types.SimpleNamespace(get_score=fetch_score, user_id=42)
       print(await rule.matches_async(thing))  # True

   asyncio.run(main())

.. note::
   Async callables only work with :py:meth:`~engine.Rule.evaluate_async` (and
   :py:meth:`~engine.Rule.matches_async` / :py:meth:`~engine.Rule.filter_async`). The synchronous
   :py:meth:`~engine.Rule.evaluate` will not ``await`` the result.

Async Methods on the ``thing`` Object
--------------------------------------
If the object passed to :py:meth:`~engine.Rule.evaluate_async` has async bound methods, those
methods can be called directly from the rule expression. The engine automatically awaits the
coroutine returned by the method call.

This requires the context's resolver to return the method object when the symbol is looked up.
The built-in :py:func:`~engine.resolve_attribute` resolver does this automatically via
``getattr``.

.. code-block:: python

   import asyncio
   import decimal
   import rule_engine

   class UserProfile:
       async def risk_score(self):
           # simulate an async computation or I/O
           await asyncio.sleep(0)
           return decimal.Decimal('72')

   context = rule_engine.Context(resolver=rule_engine.resolve_attribute)
   rule = rule_engine.Rule('risk_score() >= 70', context=context)

   async def main():
       profile = UserProfile()
       print(await rule.matches_async(profile))  # True

   asyncio.run(main())

Methods that accept arguments work the same way — pass the arguments in the expression as usual:

.. code-block:: python

   class Pricer:
       async def quote(self, quantity):
           await asyncio.sleep(0)
           return decimal.Decimal(str(quantity)) * decimal.Decimal('9.99')

   context = rule_engine.Context(resolver=rule_engine.resolve_attribute)
   rule = rule_engine.Rule('quote(5) < 60', context=context)

   asyncio.run(rule.matches_async(Pricer()))  # True (49.95 < 60)

Nested objects are also supported — the engine will resolve each level of attribute access in
turn and await the final coroutine:

.. code-block:: python

   import types

   thing = types.SimpleNamespace(service=MyAsyncService())
   rule = rule_engine.Rule('service.compute() > 0', context=context)
   await rule.evaluate_async(thing)

.. note::
   Sync methods work identically under :py:meth:`~engine.Rule.evaluate_async` — the engine
   checks :py:func:`inspect.isawaitable` on the return value and only awaits when needed, so
   there is no need to change existing sync methods.

filter_async
------------
:py:meth:`~engine.Rule.filter_async` is an async generator that yields matching items one at a
time, preserving memory efficiency for large collections:

.. code-block:: python

   import asyncio
   import rule_engine

   rule = rule_engine.Rule('age >= 18')

   people = [
       {'name': 'Alice', 'age': 30},
       {'name': 'Bob',   'age': 15},
       {'name': 'Carol', 'age': 22},
   ]

   async def main():
       async for person in rule.filter_async(people):
           print(person['name'])  # Alice, Carol

   asyncio.run(main())

   # or collect all results at once
   async def collect():
       return [p async for p in rule.filter_async(people)]

   asyncio.run(collect())  # [{'name': 'Alice', ...}, {'name': 'Carol', ...}]

Concurrent Evaluations
-----------------------
Because :py:class:`~engine.Context` now uses :py:mod:`contextvars` internally instead of
:py:mod:`threading`, per-evaluation state (regex capture groups stored in ``$re_groups``,
comprehension variable scopes) is isolated per :class:`asyncio.Task`. This means it is safe to
evaluate the same rule against multiple objects concurrently using :func:`asyncio.gather`:

.. code-block:: python

   import asyncio
   import rule_engine

   async def slow_resolver(thing, name):
       await asyncio.sleep(0.01)   # simulate latency
       return thing[name]

   context = rule_engine.Context(resolver=slow_resolver)
   rule = rule_engine.Rule('value > 5', context=context)

   async def main():
       # both evaluations run concurrently — their state never collides
       results = await asyncio.gather(
           rule.matches_async({'value': 10}),
           rule.matches_async({'value': 3}),
       )
       print(results)  # [True, False]

   asyncio.run(main())

$re_groups in Async Context
-----------------------------
The ``$re_groups`` builtin works correctly in async evaluation. Each concurrent evaluation keeps
its own copy of the captured groups:

.. code-block:: python

   import asyncio
   import rule_engine

   context = rule_engine.Context()
   rule = rule_engine.Rule(r'label =~ "(\w+)-(\d+)" and $re_groups[0] == "ticket"')

   async def main():
       result = await rule.evaluate_async({'label': 'ticket-42'})
       print(result)  # True

   asyncio.run(result)

Compatibility with the Sync API
---------------------------------
The async API is purely additive. Every existing sync call site continues to work unchanged:

.. code-block:: python

   rule = rule_engine.Rule('x > 0')

   # sync — unchanged
   rule.matches({'x': 1})      # True
   rule.evaluate({'x': 1})     # True
   list(rule.filter([...]))    # [...]

   # async — new
   await rule.matches_async({'x': 1})
   await rule.evaluate_async({'x': 1})
   [x async for x in rule.filter_async([...])]

The same :py:class:`~engine.Context` object (and the same :py:class:`~engine.Rule` object) can be
shared freely between sync and async call sites.

Limitations
-----------
* **Async callables in sync evaluation** — If a callable inside a rule expression is an
  ``async def``, calling :py:meth:`~engine.Rule.evaluate` (sync) will return the unawaited
  coroutine object rather than the actual result. Use
  :py:meth:`~engine.Rule.evaluate_async` when async callables are involved.

* **Nested evaluate_async calls** — If one :py:meth:`~engine.Rule.evaluate_async` call spawns
  another (e.g. a resolver calls ``evaluate_async`` internally), the inner call will create its
  own independent state as long as it is run as a separate :class:`asyncio.Task` (e.g. via
  :func:`asyncio.create_task` or :func:`asyncio.gather`). Direct ``await`` chains share the same
  task context.
