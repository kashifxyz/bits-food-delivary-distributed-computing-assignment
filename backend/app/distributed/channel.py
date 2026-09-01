import asyncio
from typing import List, Optional
from backend.app.models.message import Message

class Channel:
    """
    Reliable, FIFO directed communication channel from sender_id to receiver_id (Pi -> Pj).
    Supports Chandy-Lamport snapshot recording of in-transit messages.
    """
    def __init__(self, sender_id: int, receiver_id: int):
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.channel_key = f"{sender_id}->{receiver_id}"
        self._queue: asyncio.Queue[Message] = asyncio.Queue()
        
        # Snapshot recording state
        self._is_recording: bool = False
        self._recorded_messages: List[Message] = []
        self._recording_completed: bool = False
        self._all_messages_history: List[Message] = []

    async def send(self, message: Message) -> None:
        """Enqueues a message into the channel."""
        self._all_messages_history.append(message)
        await self._queue.put(message)

    async def receive(self) -> Message:
        """
        Dequeues a message from the channel.
        If recording is active and the message is NOT a MARKER, it is saved in recorded_messages.
        """
        message = await self._queue.get()
        if self._is_recording and message.message_type.value != "MARKER":
            self._recorded_messages.append(message)
        return message

    def peek_pending(self) -> List[Message]:
        """Returns messages currently buffered in the channel queue."""
        # Note: asyncio.Queue._queue is the internal deque
        return list(self._queue._queue)

    def start_recording(self) -> None:
        """Starts recording messages arriving on this channel (for Chandy-Lamport)."""
        self._is_recording = True
        self._recording_completed = False
        self._recorded_messages = []

    def stop_recording(self) -> List[Message]:
        """Stops recording and returns the captured in-transit messages."""
        self._is_recording = False
        self._recording_completed = True
        return list(self._recorded_messages)

    def is_recording(self) -> bool:
        return self._is_recording

    def is_recording_completed(self) -> bool:
        return self._recording_completed

    def get_recorded_messages(self) -> List[Message]:
        return list(self._recorded_messages)

    def clear(self) -> None:
        """Clears all messages in the channel."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._is_recording = False
        self._recording_completed = False
        self._recorded_messages = []
        self._all_messages_history = []
