# Benchmarks, to be run by codspeed.io in CI

Benchmarks are run using `pytest`: `pytest benchmarks/`.
This is unlike normal Twisted tests, that use `trial`.

## Running benchmarks as part of CI

In CI, we install `pytest-codspeed` run the benchmarks, using GitHub Actions.
The tests are executed on GitHub VMs and the reports are sent to the codspeed.io cloud.

Note that as of mid-2024, codspeed.io uses a simulated CPU (Cachegrind) to run tests, so the measures of performance are not suitable for optimizing low-level compiled code.

## Running benchmarks locally

You can run benchmarks locally by installing `pytest-benchmark` and then running `pytest benchmarks/`.
`tox -e benchmark` does this automatically.
Unlike `pytest-codspeed`, the results are specific to your computer, but they're helpful for local before/after comparisons.
And `pytest-codspeed` outputs nothing when run locally, at least at the time of writing (May 2024).

## Writing benchmarks

See the [Codspeed documentation](https://docs.codspeed.io/benchmarks/python).

Note that the `@pytest.mark.benchmark` style of benchmark doesn't work with `pytest-benchmark`, so you should not use it.
Instead, use the `benchmark` pytest fixture (i.e. an argument with that name to the test functions).
