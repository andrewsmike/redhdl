class VHDLError(BaseException):
    pass


class InvalidAssignmentError(VHDLError):
    pass


class UnsupportedAssignmentExprError(InvalidAssignmentError):
    pass


class InvalidAssignmentBitrangeError(InvalidAssignmentError):
    pass
