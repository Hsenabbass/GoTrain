# M4 workspace: UI preparation record

**Status:** UI preparation was accepted and integrated on main. Current M4 scope,
verification and next action are owned by the [M4 product handoff](m4-product.md#handoff).
**GitHub:** [M4](https://github.com/Hsenabbass/GoTrain/milestone/4)

## Accepted direction

The original simplified composer preview was approved on 2026-10-31. Later user
instructions added a neutral conversation timeline and saved-chat sidebar. The
workspace now connects supported attachments and task clarification to bounded
jobs, progress, prediction, model history and downloads. There is no dataset grid,
game, dashboard or simulated result.

Early per-step confirmation gates were superseded by authorization for the
remaining M4 implementation. All work stays on main; agent/training execution
stays on SageMaker. Source history preserves the original preview and decisions.
The disconnected local preview remains a design view, not a live training service.

## Current handoff

Earlier core acceptance and recovery receipts are in [M4 evidence](../m4-evidence.json).
The latest missing-attachment, reconnect and chat-switch fixes are implemented but
untested at the user's request. The custom segmentation package's independent
download hash remains pending. 4.2–4.3 stay open for these checks; M5 has not started.
Do not treat previous cloud checks as verification of the follow-up source changes.
