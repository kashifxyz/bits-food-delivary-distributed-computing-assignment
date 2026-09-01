import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, TYPE_CHECKING
from backend.app.models.snapshot import GlobalSnapshot, ProcessSnapshot, ChannelSnapshot
from backend.app.models.message import Message, MessageType
from backend.app.models.event import Event, EventType
from backend.app.snapshot.consistency import ConsistencyChecker

if TYPE_CHECKING:
    from backend.app.distributed.process_manager import ProcessManager

logger = logging.getLogger("SnapshotManager")

class SnapshotManager:
    """
    Executes the Chandy-Lamport Distributed Snapshot Algorithm for reliable FIFO channels.
    Coordinates local state recording, marker message propagation, channel state recording,
    and causal consistency validation.
    """
    def __init__(self, process_manager: Optional['ProcessManager'] = None):
        self.process_manager = process_manager
        self.snapshots: Dict[str, GlobalSnapshot] = {}
        self.active_snapshot_id: Optional[str] = None
        
        # Tracking per snapshot: {snapshot_id: {pid: bool}}
        self._process_recorded: Dict[str, Dict[int, bool]] = {}
        # Tracking incoming marker count per process: {snapshot_id: {pid: set(sender_ids)}}
        self._markers_received: Dict[str, Dict[int, set]] = {}
        self._lock = asyncio.Lock()

    def set_process_manager(self, process_manager: 'ProcessManager'):
        self.process_manager = process_manager

    async def initiate_snapshot(self, initiator_id: int) -> GlobalSnapshot:
        """
        Step 1 & 2 of Chandy-Lamport:
        Initiator P_i records its local state and sends MARKERs to all outgoing channels.
        """
        if not self.process_manager:
            raise RuntimeError("ProcessManager not bound to SnapshotManager")

        async with self._lock:
            snapshot_id = f"SNAP-{uuid.uuid4().hex[:6].upper()}"
            self.active_snapshot_id = snapshot_id
            
            global_snap = GlobalSnapshot(
                snapshot_id=snapshot_id,
                initiated_by=initiator_id,
                status="IN_PROGRESS"
            )
            self.snapshots[snapshot_id] = global_snap
            self._process_recorded[snapshot_id] = {}
            self._markers_received[snapshot_id] = {pid: set() for pid in self.process_manager.processes.keys()}
            
            logger.info(f"SNAPSHOT_INITIATED: {snapshot_id} by P{initiator_id}")

            # Record initiator's local process state
            initiator = self.process_manager.get_process(initiator_id)
            if not initiator:
                raise ValueError(f"Unknown initiator process P{initiator_id}")
                
            proc_snap = initiator.capture_process_snapshot()
            global_snap.process_states[initiator_id] = proc_snap
            self._process_recorded[snapshot_id][initiator_id] = True
            
            # Start recording on all incoming channels to initiator
            for inc_ch in self.process_manager.message_bus.get_incoming_channels(initiator_id):
                inc_ch.start_recording()

            # Record event
            event = Event(
                process_id=initiator_id,
                event_type=EventType.SNAPSHOT_START,
                description=f"Initiated Global Snapshot {snapshot_id}",
                vector_clock=initiator.vector_clock.get_clock(),
                metadata={"snapshot_id": snapshot_id}
            )
            await self.process_manager.event_manager.record_event(event)

            # Send MARKER on all outgoing channels from initiator
            for dst_pid in self.process_manager.processes.keys():
                if dst_pid != initiator_id:
                    await initiator.send_msg(
                        receiver_id=dst_pid,
                        message_type=MessageType.MARKER,
                        payload={"snapshot_id": snapshot_id, "initiator_id": initiator_id},
                        snapshot_id=snapshot_id
                    )

            # Check if immediately completed (single process or test cases)
            self._check_snapshot_completion(snapshot_id)
            return global_snap

    async def handle_marker_received(self, receiver_id: int, sender_id: int, marker_msg: Message):
        """
        Step 3 & 4 of Chandy-Lamport:
        Invoked when receiver_id receives a MARKER message from sender_id.
        """
        snapshot_id = marker_msg.snapshot_id or self.active_snapshot_id
        if not snapshot_id or snapshot_id not in self.snapshots:
            return

        async with self._lock:
            global_snap = self.snapshots[snapshot_id]
            receiver = self.process_manager.get_process(receiver_id)
            if not receiver:
                return

            has_recorded = self._process_recorded[snapshot_id].get(receiver_id, False)
            ch_key = f"{sender_id}->{receiver_id}"
            channel = self.process_manager.message_bus.get_channel(sender_id, receiver_id)

            if not has_recorded:
                # FIRST marker received at this process
                # 1. Record receiver's local process state
                proc_snap = receiver.capture_process_snapshot()
                global_snap.process_states[receiver_id] = proc_snap
                self._process_recorded[snapshot_id][receiver_id] = True
                
                # 2. Mark incoming channel C(sender->receiver) as empty state
                global_snap.channel_states[ch_key] = ChannelSnapshot(
                    sender_id=sender_id,
                    receiver_id=receiver_id,
                    channel_key=ch_key,
                    messages=[],
                    is_recording=False,
                    recording_completed=True
                )
                
                # 3. Start recording on all other incoming channels
                for inc_ch in self.process_manager.message_bus.get_incoming_channels(receiver_id):
                    if inc_ch.sender_id != sender_id:
                        inc_ch.start_recording()

                # 4. Send MARKER messages out on all outgoing channels
                for dst_pid in self.process_manager.processes.keys():
                    if dst_pid != receiver_id:
                        await receiver.send_msg(
                            receiver_id=dst_pid,
                            message_type=MessageType.MARKER,
                            payload={"snapshot_id": snapshot_id, "initiator_id": global_snap.initiated_by},
                            snapshot_id=snapshot_id
                        )
            else:
                # SUBSEQUENT marker received on this incoming channel
                # Stop recording on this channel and capture collected messages
                if channel:
                    recorded_msgs = channel.stop_recording()
                else:
                    recorded_msgs = []
                    
                global_snap.channel_states[ch_key] = ChannelSnapshot(
                    sender_id=sender_id,
                    receiver_id=receiver_id,
                    channel_key=ch_key,
                    messages=recorded_msgs,
                    is_recording=False,
                    recording_completed=True
                )

            # Record sender as having delivered marker to receiver
            self._markers_received[snapshot_id][receiver_id].add(sender_id)
            self._check_snapshot_completion(snapshot_id)

    def _check_snapshot_completion(self, snapshot_id: str):
        """
        Step 5 & 6: Checks if all processes and all directed channels have finished recording.
        """
        global_snap = self.snapshots.get(snapshot_id)
        if not global_snap or global_snap.status == "COMPLETED":
            return

        all_pids = set(self.process_manager.processes.keys())
        recorded_pids = set(global_snap.process_states.keys())
        
        # Check if all processes recorded
        if recorded_pids != all_pids:
            return

        # Check if all directed channels have recorded
        all_channels = self.process_manager.message_bus.get_all_channels()
        for ch_key, ch in all_channels.items():
            if ch_key not in global_snap.channel_states:
                # Not yet completed marker arrival for this channel
                return

        # If we reach here, snapshot is complete!
        global_snap.status = "COMPLETED"
        global_snap.completed_at = datetime.now(timezone.utc).isoformat()
        self.active_snapshot_id = None
        
        # Run Consistency Checker
        all_events = self.process_manager.event_manager.get_all_events()
        consistency_res = ConsistencyChecker.verify(global_snap, all_events)
        global_snap.consistency = consistency_res
        
        logger.info(f"SNAPSHOT_COMPLETED: {snapshot_id} (Consistent={consistency_res.consistent})")

    def get_snapshot(self, snapshot_id: str) -> Optional[GlobalSnapshot]:
        return self.snapshots.get(snapshot_id)

    def get_all_snapshots(self) -> List[GlobalSnapshot]:
        return list(self.snapshots.values())

    def get_latest_snapshot(self) -> Optional[GlobalSnapshot]:
        if not self.snapshots:
            return None
        return list(self.snapshots.values())[-1]

    def reset(self):
        self.snapshots.clear()
        self.active_snapshot_id = None
        self._process_recorded.clear()
        self._markers_received.clear()
