from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import asyncio
import logging
from backend.app.distributed.channel import Channel
from backend.app.models.message import Message, MessageType

logger = logging.getLogger("MessageBus")

class MessageBus(ABC):
    @abstractmethod
    async def send_message(self, message: Message) -> None:
        pass

    @abstractmethod
    def get_channel(self, sender_id: int, receiver_id: int) -> Optional[Channel]:
        pass

    @abstractmethod
    def get_all_channels(self) -> Dict[str, Channel]:
        pass

    @abstractmethod
    def get_incoming_channels(self, process_id: int) -> List[Channel]:
        pass

    @abstractmethod
    def get_outgoing_channels(self, process_id: int) -> List[Channel]:
        pass

class LocalMessageBus(MessageBus):
    """
    In-memory asynchronous message bus using directed FIFO channels between processes.
    Enables decoupled logical processes communicating solely via message passing.
    """
    def __init__(self, process_ids: List[int]):
        self.process_ids = process_ids
        self.channels: Dict[str, Channel] = {}
        self._init_channels()

    def _init_channels(self):
        for src in self.process_ids:
            for dst in self.process_ids:
                if src != dst:
                    key = f"{src}->{dst}"
                    self.channels[key] = Channel(sender_id=src, receiver_id=dst)

    def get_channel(self, sender_id: int, receiver_id: int) -> Optional[Channel]:
        key = f"{sender_id}->{receiver_id}"
        return self.channels.get(key)

    def get_all_channels(self) -> Dict[str, Channel]:
        return self.channels

    def get_incoming_channels(self, process_id: int) -> List[Channel]:
        return [ch for ch in self.channels.values() if ch.receiver_id == process_id]

    def get_outgoing_channels(self, process_id: int) -> List[Channel]:
        return [ch for ch in self.channels.values() if ch.sender_id == process_id]

    async def send_message(self, message: Message) -> None:
        channel = self.get_channel(message.sender_id, message.receiver_id)
        if not channel:
            raise ValueError(f"No channel exists for route {message.sender_id} -> {message.receiver_id}")
        logger.info(f"Routing message {message.id} ({message.message_type}) from P{message.sender_id} to P{message.receiver_id}")
        await channel.send(message)

    def reset(self):
        for ch in self.channels.values():
            ch.clear()
