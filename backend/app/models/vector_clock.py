from enum import Enum
from typing import List, Tuple
from pydantic import BaseModel, Field

class CausalRelation(str, Enum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    CONCURRENT = "CONCURRENT"
    SAME = "SAME"

class VectorClockModel(BaseModel):
    clock: List[int] = Field(default_factory=list, description="Vector clock values per process")
    
    def copy(self) -> "VectorClockModel":
        return VectorClockModel(clock=list(self.clock))

def happens_before(a: List[int], b: List[int]) -> bool:
    """
    Returns True if vector clock 'a' causally happens before vector clock 'b' (a -> b):
    a[i] <= b[i] for all i, AND a[i] < b[i] for at least one i.
    """
    if len(a) != len(b):
        raise ValueError(f"Clock dimension mismatch: {len(a)} vs {len(b)}")
    
    all_less_or_equal = all(x <= y for x, y in zip(a, b))
    at_least_one_less = any(x < y for x, y in zip(a, b))
    
    return all_less_or_equal and at_least_one_less

def are_equal(a: List[int], b: List[int]) -> bool:
    return a == b

def is_concurrent(a: List[int], b: List[int]) -> bool:
    """
    Returns True if neither vector clock causally precedes the other and they are not identical.
    """
    if are_equal(a, b):
        return False
    return not happens_before(a, b) and not happens_before(b, a)

def compare_clocks(a: List[int], b: List[int]) -> CausalRelation:
    """
    Determines the causal relationship between two vector clocks:
    - SAME: a == b
    - BEFORE: a -> b
    - AFTER: b -> a
    - CONCURRENT: a || b
    """
    if are_equal(a, b):
        return CausalRelation.SAME
    if happens_before(a, b):
        return CausalRelation.BEFORE
    if happens_before(b, a):
        return CausalRelation.AFTER
    return CausalRelation.CONCURRENT
