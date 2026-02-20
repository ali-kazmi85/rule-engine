#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  tests/async_support.py
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following disclaimer
#    in the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of the project nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import asyncio
import unittest

import rule_engine.engine as engine
import rule_engine.errors as errors

__all__ = (
	'AsyncResolverTests',
	'AsyncFunctionCallTests',
	'AsyncBoundMethodTests',
	'AsyncConcurrencyTests',
	'AsyncReGroupsTests',
)


def _run(coro):
	return asyncio.run(coro)


async def _async_resolver(thing, name):
	await asyncio.sleep(0)  # simulate async I/O
	return engine.resolve_item(thing, name)


class AsyncResolverTests(unittest.TestCase):
	def test_evaluate_async_with_sync_resolver(self):
		rule = engine.Rule('age > 18')
		result = _run(rule.evaluate_async({'age': 25}))
		self.assertTrue(result)

	def test_evaluate_async_with_sync_resolver_false(self):
		rule = engine.Rule('age > 18')
		result = _run(rule.evaluate_async({'age': 10}))
		self.assertFalse(result)

	def test_evaluate_async_with_async_resolver(self):
		ctx = engine.Context(resolver=_async_resolver)
		rule = engine.Rule('age > 18', context=ctx)
		result = _run(rule.evaluate_async({'age': 25}))
		self.assertTrue(result)

	def test_evaluate_async_with_async_resolver_false(self):
		ctx = engine.Context(resolver=_async_resolver)
		rule = engine.Rule('age > 18', context=ctx)
		result = _run(rule.evaluate_async({'age': 10}))
		self.assertFalse(result)

	def test_matches_async_true(self):
		rule = engine.Rule('name == "Alice"')
		result = _run(rule.matches_async({'name': 'Alice'}))
		self.assertTrue(result)

	def test_matches_async_false(self):
		rule = engine.Rule('name == "Alice"')
		result = _run(rule.matches_async({'name': 'Bob'}))
		self.assertFalse(result)

	def test_filter_async(self):
		rule = engine.Rule('age >= 18')
		things = [{'age': 10}, {'age': 20}, {'age': 5}, {'age': 30}]

		async def collect():
			return [item async for item in rule.filter_async(things)]

		results = _run(collect())
		self.assertEqual(results, [{'age': 20}, {'age': 30}])

	def test_evaluate_async_string_expression(self):
		rule = engine.Rule('greeting == "hello"')
		result = _run(rule.evaluate_async({'greeting': 'hello'}))
		self.assertTrue(result)

	def test_evaluate_async_arithmetic(self):
		rule = engine.Rule('x * 2 + 1 > 5')
		result = _run(rule.evaluate_async({'x': 3}))
		self.assertTrue(result)

	def test_evaluate_async_logic(self):
		rule = engine.Rule('a and b')
		self.assertTrue(_run(rule.evaluate_async({'a': True, 'b': True})))
		self.assertFalse(_run(rule.evaluate_async({'a': True, 'b': False})))

	def test_evaluate_async_logic_or(self):
		rule = engine.Rule('a or b')
		self.assertTrue(_run(rule.evaluate_async({'a': False, 'b': True})))
		self.assertFalse(_run(rule.evaluate_async({'a': False, 'b': False})))

	def test_evaluate_async_ternary(self):
		rule = engine.Rule('x > 0 ? "positive" : "non-positive"')
		result = _run(rule.evaluate_async({'x': 5}))
		self.assertEqual(result, 'positive')

	def test_evaluate_async_contains(self):
		rule = engine.Rule('"foo" in tags')
		result = _run(rule.evaluate_async({'tags': ('foo', 'bar')}))
		self.assertTrue(result)

	def test_evaluate_async_array_comprehension(self):
		rule = engine.Rule('[x for x in items if x > 2]')
		result = _run(rule.evaluate_async({'items': (1, 2, 3, 4, 5)}))
		self.assertEqual(result, (3, 4, 5))

	def test_symbol_resolution_error_async(self):
		rule = engine.Rule('missing_symbol > 0')
		with self.assertRaises(errors.SymbolResolutionError):
			_run(rule.evaluate_async({'age': 5}))


class AsyncFunctionCallTests(unittest.TestCase):
	def test_sync_callable_in_async_context(self):
		"""A sync callable should still work when evaluated via evaluate_async."""
		import decimal

		def double(x):
			return x * decimal.Decimal('2')

		ctx = engine.Context(resolver=engine.resolve_attribute)
		rule = engine.Rule('double(value) > 10', context=ctx)

		import types
		thing = types.SimpleNamespace(double=double, value=decimal.Decimal('6'))
		result = _run(rule.evaluate_async(thing))
		self.assertTrue(result)

	def test_async_callable_in_expression(self):
		"""An async callable referenced via the resolver should work with evaluate_async."""
		import decimal

		async def fetch_multiplier(x):
			await asyncio.sleep(0)
			return x * decimal.Decimal('3')

		ctx = engine.Context(resolver=engine.resolve_attribute)
		rule = engine.Rule('multiply(value) > 10', context=ctx)

		import types
		thing = types.SimpleNamespace(multiply=fetch_multiplier, value=decimal.Decimal('4'))
		result = _run(rule.evaluate_async(thing))
		self.assertTrue(result)

	def test_attribute_access_async(self):
		"""Built-in attribute access (e.g. .length) works in async evaluation."""
		rule = engine.Rule('name.length > 3')
		result = _run(rule.evaluate_async({'name': 'Alice'}))
		self.assertTrue(result)

	def test_attribute_access_async_false(self):
		rule = engine.Rule('name.length > 10')
		result = _run(rule.evaluate_async({'name': 'Bob'}))
		self.assertFalse(result)


class AsyncBoundMethodTests(unittest.TestCase):
	def test_bound_async_method_no_args(self):
		"""A no-argument async bound method on thing is called and awaited correctly."""
		import decimal

		class Scorer:
			async def score(self):
				await asyncio.sleep(0)
				return decimal.Decimal('95')

		ctx = engine.Context(resolver=engine.resolve_attribute)
		rule = engine.Rule('score() > 90', context=ctx)
		self.assertTrue(_run(rule.evaluate_async(Scorer())))

	def test_bound_async_method_with_args(self):
		"""An async bound method that takes arguments works correctly."""
		import decimal

		class Calculator:
			async def multiply(self, x):
				await asyncio.sleep(0)
				return decimal.Decimal(str(x)) * decimal.Decimal('3')

		ctx = engine.Context(resolver=engine.resolve_attribute)
		rule = engine.Rule('multiply(4) > 10', context=ctx)
		self.assertTrue(_run(rule.evaluate_async(Calculator())))

	def test_bound_async_method_on_nested_object(self):
		"""Async method on a nested attribute of thing is called and awaited."""
		import decimal
		import types

		class Service:
			async def get_value(self):
				await asyncio.sleep(0)
				return decimal.Decimal('7')

		thing = types.SimpleNamespace(svc=Service())
		ctx = engine.Context(resolver=engine.resolve_attribute)
		rule = engine.Rule('svc.get_value() > 5', context=ctx)
		self.assertTrue(_run(rule.evaluate_async(thing)))

	def test_sync_method_still_works_in_async_evaluation(self):
		"""A regular (sync) bound method also works fine under evaluate_async."""
		import decimal

		class Scorer:
			def score(self):
				return decimal.Decimal('80')

		ctx = engine.Context(resolver=engine.resolve_attribute)
		rule = engine.Rule('score() > 70', context=ctx)
		self.assertTrue(_run(rule.evaluate_async(Scorer())))


class AsyncConcurrencyTests(unittest.TestCase):
	def test_regex_groups_isolated_across_concurrent_evaluations(self):
		"""regex_groups must be isolated between concurrent async evaluations."""
		context = engine.Context()
		rule = engine.Rule(r'words =~ "(\\w+) \\w+"', context=context)

		async def eval_and_capture(thing):
			result = await rule.evaluate_async(thing)
			# read regex_groups immediately after evaluation completes
			return context._tls.regex_groups

		async def run():
			# run two evaluations concurrently
			groups1, groups2 = await asyncio.gather(
				eval_and_capture({'words': 'FirstTask test'}),
				eval_and_capture({'words': 'SecondTask test'}),
			)
			return groups1, groups2

		groups1, groups2 = _run(run())
		# each task should have seen its own regex_groups
		self.assertIn(groups1, (('FirstTask',), ('SecondTask',)))
		self.assertIn(groups2, (('FirstTask',), ('SecondTask',)))

	def test_assignment_scopes_isolated_across_concurrent_evaluations(self):
		"""assignment_scopes from comprehensions must not leak across concurrent evaluations."""
		context = engine.Context()
		rule = engine.Rule('[x for x in items][0]', context=context)

		async def eval_and_check(thing):
			result = await rule.evaluate_async(thing)
			# assignment scope must be cleared after evaluation
			return result, len(context._tls.assignment_scopes)

		async def run():
			results = await asyncio.gather(
				eval_and_check({'items': (10, 20, 30)}),
				eval_and_check({'items': (40, 50, 60)}),
			)
			return results

		results = _run(run())
		for value, scope_len in results:
			self.assertEqual(scope_len, 0)
			self.assertIn(value, (10, 40))

	def test_concurrent_evaluations_do_not_interfere(self):
		"""Two concurrent evaluations with different data should each return the correct result."""
		import asyncio

		async def slow_resolver(thing, name):
			await asyncio.sleep(0.01)
			return engine.resolve_item(thing, name)

		ctx = engine.Context(resolver=slow_resolver)
		rule = engine.Rule('value > 5', context=ctx)

		async def run():
			result_a, result_b = await asyncio.gather(
				rule.matches_async({'value': 10}),
				rule.matches_async({'value': 3}),
			)
			return result_a, result_b

		result_a, result_b = _run(run())
		self.assertTrue(result_a)
		self.assertFalse(result_b)


class AsyncReGroupsTests(unittest.TestCase):
	def test_re_groups_builtin_in_async_context(self):
		"""$re_groups should be populated correctly after a regex match in async evaluation."""
		context = engine.Context()
		rule = engine.Rule(r'words =~ "(\\w+) (\\w+)" and $re_groups[0] == "Hello"', context=context)
		result = _run(rule.evaluate_async({'words': 'Hello World'}))
		self.assertTrue(result)

	def test_re_groups_builtin_no_match_in_async_context(self):
		"""$re_groups should be empty / evaluation should be false when regex does not match."""
		context = engine.Context()
		rule = engine.Rule(r'words =~ "(\\d+)"', context=context)
		result = _run(rule.evaluate_async({'words': 'no digits here'}))
		self.assertFalse(result)

	def test_re_groups_async_resolver(self):
		"""$re_groups works when resolver is an async coroutine."""
		context = engine.Context(resolver=_async_resolver)
		rule = engine.Rule(r'words =~ "(\\w+) \\w+" and $re_groups[0] == "async"', context=context)
		result = _run(rule.evaluate_async({'words': 'async test'}))
		self.assertTrue(result)
