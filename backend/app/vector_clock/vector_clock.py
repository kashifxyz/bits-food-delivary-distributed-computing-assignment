import threading
from typing import List, Tuple
from backend.app.models.vector_clock import CausalRelation, happens_before, is_concurrent, are_equal, compare_clocks

class VectorClock:
    """
    Vector Clock implementation from first principles for distributed logical time tracking.
    Process IDs are 1-indexed (e.g. 1, 2, 3, 4) mapping to indices 0, 1, 2, 3.
    """
    def __init__(self, process_id: int, num_processes: int = 4):
        if process_id < 1 or process_id > num_processes:
            raise ValueError(f"Process ID must be between 1 and {num_processes}, got {process_id}")
        self.process_id = process_id
        self.num_processes = num_processes
        self.process_index = process_id - 1
        self._clock: List[int] = [0] * num_processes
        self._lock = threading.Lock()

    def get_clock(self) -> List[int]:
        """Returns a copy of the current vector clock."""
        with self._lock:
            return list(self._clock)

    def tick_internal(self) -> List[int]:
        """
        Internal event rule:
        clock[process_index] += 1
        """
        with self._lock:
            self._clock[self.process_index] += 1
            return list(self._clock)

    def tick_send(self) -> List[int]:
        """
        Send event rule:
        clock[process_index] += 1 before attaching to outgoing message.
        """
        with self._lock:
            self._clock[self.process_index] += 1
            return list(self._clock)

    def tick_receive(self, received_clock: List[int]) -> List[int]:
        """
        Receive event rule:
        For all k: clock[k] = max(clock[k], received_clock[k])
        Then: clock[process_index] += 1
        """
        if len(received_clock) != self.num_processes:
            raise ValueError(f"Received clock length {len(received_clock)} does not match {self.num_processes}")
        
        with self._lock:
            for k in range(self.num_processes):
                self._clock[k] = max(self._clock[k], received_clock[k])
            self._clock[self.process_index] += 1
            return list(self._clock)

    def reset(self, initial_values: List[int] = None):
        """Resets the vector clock."""
        with self._lock:
            if initial_values is not None:
                if len(initial_values) != self.num_processes:
                    raise ValueError("Initial values length mismatch")
                self._clock = list(initial_values)
            else:
                self._clock = [0] * self.num_processes

    def __repr__(self) -> str:
        return f"VectorClock(P{self.process_id}, clock={self.get_clock()})"

    @staticmethod
    def happens_before(a: List[int], b: List[int]) -> bool:
        return happens_before(a, b)

    @staticmethod
    def is_concurrent(a: List[int], b: List[int]) -> bool:
        return is_concurrent(a, b)

    @staticmethod
    def are_equal(a: List[int], b: List[int]) -> bool:
        return are_equal(a, b)

    @staticmethod
    def compare(a: List[int], b: List[int]) -> CausalRelation:
        return compare_clocks(a, b)
