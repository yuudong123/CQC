SET SESSION TRANSACTION READ ONLY;
START TRANSACTION READ ONLY;
SELECT 'FAILED_COUNT' AS __qa_section;
SELECT COUNT(*) AS failed_control_rows FROM control_attempts WHERE control_status='FAILED';
SELECT 'FAILED_CONTROLS' AS __qa_section;
SELECT c.id,c.inspection_id,c.command_id,c.attempt_no,c.requested_bin_code,c.control_status,c.requested_at,c.responded_at,i.source_reference,i.used_frame_count,i.model_version,i.persistence_status FROM control_attempts c LEFT JOIN inspections i ON i.inspection_id=c.inspection_id WHERE c.control_status='FAILED' ORDER BY c.id DESC LIMIT 20;
SELECT 'INFERENCE_ALTERNATIVES' AS __qa_section;
SELECT c.id,c.inspection_id,c.command_id,c.attempt_no,c.requested_bin_code,c.control_status,c.requested_at,c.responded_at,i.source_reference,i.used_frame_count,i.model_version,i.error_code,i.persistence_status FROM control_attempts c JOIN inspections i ON i.inspection_id=c.inspection_id WHERE c.inspection_id IN ('qa-be-10081626s-ins01-FS-15.0','qa-be-10081526-ins08') ORDER BY c.inspection_id,c.attempt_no,c.id;
COMMIT;
