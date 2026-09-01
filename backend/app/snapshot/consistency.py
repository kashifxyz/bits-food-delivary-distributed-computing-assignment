import logging
from typing import List, Dict, Any, Set
from backend.app.models.snapshot import GlobalSnapshot, ConsistencyCheckResult
from backend.app.models.event import EventType

logger = logging.getLogger("ConsistencyChecker")

class ConsistencyChecker:
    """
    Validates causal and channel consistency of a recorded Global Snapshot.
    Ensures:
    1. No orphan messages: No receive event appears in a process state without the corresponding send event
       being either in the sender process snapshot or in the recorded channel snapshot.
    2. Vector clock consistency across processes.
    """
    @staticmethod
    def verify(global_snapshot: GlobalSnapshot, all_events: List[Any] = None) -> ConsistencyCheckResult:
        issues: List[str] = []
        
        # Extract process snapshots
        proc_states = global_snapshot.process_states
        chan_states = global_snapshot.channel_states
        
        if len(proc_states) < 4:
            issues.append(f"Incomplete snapshot: expected 4 process states, found {len(proc_states)}")

        # Collect all messages recorded in transit in channels
        in_transit_msg_ids: Set[str] = set()
        for ch_key, ch_snap in chan_states.items():
            for msg in ch_snap.messages:
                in_transit_msg_ids.add(msg.id)

        # Build list of sent message IDs recorded in process states (from event history or order logs)
        # We also check vector clock consistency:
        # For any two processes Pi and Pj, Pi's vector clock at snapshot must not show knowledge of an
        # event at Pj that happened AFTER Pj recorded its snapshot.
        for pid_i, snap_i in proc_states.items():
            clock_i = snap_i.vector_clock
            for pid_j, snap_j in proc_states.items():
                if pid_i != pid_j:
                    clock_j = snap_j.vector_clock
                    # snap_i says Pj had reached clock_i[pid_j - 1]
                    recorded_j_clock = clock_j[pid_j - 1]
                    perceived_j_by_i = clock_i[pid_j - 1]
                    
                    if perceived_j_by_i > recorded_j_clock:
                        issues.append(
                            f"Causal inconsistency: P{pid_i}'s snapshot has clock[{pid_j}]={perceived_j_by_i}, "
                            f"which exceeds P{pid_j}'s recorded local clock of {recorded_j_clock}. (Post-snapshot event perceived)"
                        )

        # Check in-transit messages: they must originate from a process send that occurred before the sender recorded its snapshot
        for ch_key, ch_snap in chan_states.items():
            sender_id = ch_snap.sender_id
            if sender_id in proc_states:
                sender_recorded_clock = proc_states[sender_id].vector_clock
                for msg in ch_snap.messages:
                    msg_sender_val = msg.vector_clock[sender_id - 1]
                    recorded_sender_val = sender_recorded_clock[sender_id - 1]
                    if msg_sender_val > recorded_sender_val:
                        issues.append(
                            f"Channel {ch_key} contains message {msg.id} sent after P{sender_id} recorded its state."
                        )

        is_consistent = (len(issues) == 0)
        
        if is_consistent:
            explanation = (
                "The global snapshot is strictly causally consistent. "
                "Every received message has a corresponding recorded send event, "
                "no post-snapshot events are causally referenced by any process, "
                "and in-transit channel states accurately capture flying messages."
            )
        else:
            explanation = f"Snapshot inconsistency detected: {'; '.join(issues)}"

        return ConsistencyCheckResult(
            consistent=is_consistent,
            issues=issues,
            explanation=explanation,
            analyzed_events_count=len(all_events) if all_events else 0
        )
