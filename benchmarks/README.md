# Benchmarks, to be run by codspeed.io in CI

## Running benchmarks

Note that as of mid-2024, codspeed.io uses a simulated CPU (Cachegrind) to run tests, so the measures of performance are not suitable for optimizing low-level compiled code.

In CI, we use `tox -e benchmarks-ci` to run the benchmarks, using GitHub Actions.
The tests are executed on GitHub VMs and the reports are sent to the codspeed.io cloud.

You can run benchmarks locally by installing `pytest-benchmark` and then running `pytest benchmarks/`.

No reports are generated.
This is just to check the tests aren't failing.

## Writing benchmarks

See the [Codspeed documentation](https://docs.codspeed.io/benchmarks/python).

Note that the `@pytest.mark.benchmark` style of benchmark doesn't work with `pytest-benchmark`, so you should not use it.
