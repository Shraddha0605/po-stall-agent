# Discovery Notes

This project is built to demonstrate a proof of concept for PO stall detection and resolution.

Key design assumptions:
- Each GSM has their own mailbox and Slack channel.
- The system is namespaced by `gsm_id` and supports multiple GSMs.
- Language models are used only for classification/extraction and final digest composition.
- All other logic is deterministic, auditable, and idempotent.
- The app never sends email and never writes to the ERP.

This discovery-oriented repo contains the core workflow and enough connector scaffolding to run with Gmail and Slack credentials.
