import time
from functools import wraps

def retry(exceptions=(Exception,), tries=5, delay=1.0, backoff=1.8):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _tries, _delay = tries, delay
            while _tries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    print(f"[retry] {func.__name__} failed: {e} -> sleep {_delay:.2f}s")
                    time.sleep(_delay)
                    _tries -= 1
                    _delay *= backoff
            return func(*args, **kwargs)
        return wrapper
    return decorator
