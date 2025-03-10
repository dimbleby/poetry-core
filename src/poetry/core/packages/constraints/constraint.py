import operator

from typing import TYPE_CHECKING
from typing import Any
from typing import Union

from poetry.core.packages.constraints.base_constraint import BaseConstraint
from poetry.core.packages.constraints.empty_constraint import EmptyConstraint


if TYPE_CHECKING:
    from poetry.core.packages.constraints import ConstraintTypes  # noqa


class Constraint(BaseConstraint):

    OP_EQ = operator.eq
    OP_NE = operator.ne

    _trans_op_str = {"=": OP_EQ, "==": OP_EQ, "!=": OP_NE}

    _trans_op_int = {OP_EQ: "==", OP_NE: "!="}

    def __init__(self, version: str, operator: str = "==") -> None:
        if operator == "=":
            operator = "=="

        self._version = version
        self._operator = operator
        self._op = self._trans_op_str[operator]

    @property
    def version(self) -> str:
        return self._version

    @property
    def operator(self) -> str:
        return self._operator

    def allows(self, other: "ConstraintTypes") -> bool:
        is_equal_op = self._operator == "=="
        is_non_equal_op = self._operator == "!="
        is_other_equal_op = other.operator == "=="
        is_other_non_equal_op = other.operator == "!="

        if is_equal_op and is_other_equal_op:
            return self._version == other.version

        if (
            is_equal_op
            and is_other_non_equal_op
            or is_non_equal_op
            and is_other_equal_op
            or is_non_equal_op
            and is_other_non_equal_op
        ):
            return self._version != other.version

        return False

    def allows_all(self, other: "ConstraintTypes") -> bool:
        if not isinstance(other, Constraint):
            return other.is_empty()

        return other == self

    def allows_any(self, other: "ConstraintTypes") -> bool:
        if isinstance(other, Constraint):
            is_non_equal_op = self._operator == "!="
            is_other_non_equal_op = other.operator == "!="

            if is_non_equal_op and is_other_non_equal_op:
                return self._version != other.version

        return other.allows(self)

    def difference(
        self, other: "ConstraintTypes"
    ) -> Union["Constraint", "EmptyConstraint"]:
        if other.allows(self):
            return EmptyConstraint()

        return self

    def intersect(self, other: "ConstraintTypes") -> "ConstraintTypes":
        from poetry.core.packages.constraints.multi_constraint import MultiConstraint

        if isinstance(other, Constraint):
            if other == self:
                return self

            if self.operator == "!=" and other.operator == "==" and self.allows(other):
                return other

            if other.operator == "!=" and self.operator == "==" and other.allows(self):
                return self

            if other.operator == "!=" and self.operator == "!=":
                return MultiConstraint(self, other)

            return EmptyConstraint()

        return other.intersect(self)

    def union(self, other: "ConstraintTypes") -> "ConstraintTypes":
        if isinstance(other, Constraint):
            from poetry.core.packages.constraints.union_constraint import (
                UnionConstraint,
            )

            return UnionConstraint(self, other)

        return other.union(self)

    def is_any(self) -> bool:
        return False

    def is_empty(self) -> bool:
        return False

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Constraint):
            return NotImplemented

        return (self.version, self.operator) == (other.version, other.operator)

    def __hash__(self) -> int:
        return hash((self._operator, self._version))

    def __str__(self) -> str:
        op = self._operator if self._operator != "==" else ""
        return f"{op}{self._version}"
