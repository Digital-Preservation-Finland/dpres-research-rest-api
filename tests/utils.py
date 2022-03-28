"""Testing utilities"""

import time
import inspect


def wait_for(condition, timeout=1, interval=0.2):
    """
    Wait until the function `condition` evaluates to a truthy value,
    retrying every `interval` seconds until `timeout` is reached.

    :param condition: Test function called repeatedly
    :param timeout: How long to wait until failing
    :param interval: The wait period between retries
    """
    start = time.time()

    result = condition()

    while not result:
        if time.time() > (start + timeout):
            try:
                source = inspect.getsource(condition)
            except OSError:
                # Use 'repr' as fallback if we can't get a human-readable
                # Python source code for the function
                source = repr(condition)

            raise TimeoutError(
                f"Function '{source}' did not evaluate to a truthy value "
                f"in {timeout} seconds. Last value: {result}"
            )

        time.sleep(interval)

        result = condition()
