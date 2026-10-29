# Benchmarks, to be run by codspeed.io in CI

Benchmarks are run using `pytest`: `pytest benchmarks/ --codspeed`.
This is unlike normal Twisted tests, that use `trial`.

## Running benchmarks as part of CI

In CI, we install `pytest-codspeed` run the benchmarks, using GitHub Actions.
The tests are executed on GitHub VMs and the reports are sent to the codspeed.io cloud.

Note that as of mid-2024, codspeed.io uses a simulated CPU (Cachegrind) to run tests, so the measures of performance are not suitable for optimizing low-level compiled code.

## Running benchmarks locally

You can run benchmarks locally by running `tox -e benchmark`.

## Writing benchmarks

See the [Codspeed documentation](https://docs.codspeed.io/benchmarks/python).
