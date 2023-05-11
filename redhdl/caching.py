from functools import wraps


class CachingError(BaseException):
    "Expected result to be cached, but it was not."


def first_id_cached(func):
    func._cache = {}

    @wraps(func)
    def wrapper(id_obj, *args, assert_cached: bool = False, **kwargs):
        key = (id(id_obj), tuple(args), tuple(sorted(kwargs.items())))
        if key not in func._cache:
            if assert_cached:
                raise CachingError(
                    f"Expected {func} to have cached result for args {id(id_obj)} {args} {kwargs}"
                )

            try:
                func._cache[key] = (True, func(id_obj, *args, **kwargs))
            except BaseException as e:
                func._cache[key] = (False, e)

        success, result = func._cache[key]
        if success:
            return result
        else:
            raise result

    return wrapper
