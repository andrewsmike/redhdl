"""Generic bussing concepts used by naive_bussing and redstone_bussing."""


class BussingError(BaseException):
    """Any bussing-related problem."""


class BussingTimeoutError(BussingError):
    """We couldn't find the requested bus quickly enough."""


class BussingImpossibleError(BussingError):
    """The requested bus is literally impossible."""


class BussingLogicError(BussingError):
    """There's a bug in the bussing logic and something broke."""
