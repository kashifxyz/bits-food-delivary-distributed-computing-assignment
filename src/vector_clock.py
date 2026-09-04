import sys
import threading
from colorama import Fore, Style, init

# Windows consoles default to a non-UTF-8 codepage (e.g. cp1252), which
# crashes on the unicode symbols (✓, ★, →, etc.) printed across this project.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name)
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

init(autoreset=True)

class VectorClock:
    def __init__(self, process_id: int, num_processes: int = 5):
        self.process_id = process_id
        self.num_processes = num_processes
        self.clock = [0] * num_processes
        self.lock = threading.Lock()

    def increment(self) -> list:
        with self.lock:
            self.clock[self.process_id] += 1
            return self.clock.copy()

    def send_event(self) -> list:
        with self.lock:
            self.clock[self.process_id] += 1
            print(f"{Fore.GREEN}[SEND] P{self.process_id} | Clock: {self.clock}{Style.RESET_ALL}")
            return self.clock.copy()

    def receive_event(self, received_clock: list) -> list:
        if hasattr(received_clock, "get_clock"):
            received_clock = received_clock.get_clock()
        with self.lock:
            for i in range(min(self.num_processes, len(received_clock))):
                self.clock[i] = max(self.clock[i], received_clock[i])
            self.clock[self.process_id] += 1
            print(f"{Fore.CYAN}[RECV] P{self.process_id} | Clock: {self.clock}{Style.RESET_ALL}")
            return self.clock.copy()

    def internal_event(self, description: str) -> list:
        with self.lock:
            self.clock[self.process_id] += 1
            print(f"{Fore.YELLOW}[INTERNAL] P{self.process_id} | {description} | Clock: {self.clock}{Style.RESET_ALL}")
            return self.clock.copy()

    def get_clock(self) -> list:
        with self.lock:
            return self.clock.copy()

    def is_concurrent(self, other_clock) -> bool:
        if hasattr(other_clock, "get_clock"):
            other_clock = other_clock.get_clock()
        with self.lock:
            if not isinstance(other_clock, (list, tuple)) or len(other_clock) != self.num_processes:
                return False
            less_or_equal = any(self.clock[i] < other_clock[i] for i in range(self.num_processes))
            greater_or_equal = any(self.clock[i] > other_clock[i] for i in range(self.num_processes))
            return less_or_equal and greater_or_equal

    def __str__(self) -> str:
        return str(self.clock)
