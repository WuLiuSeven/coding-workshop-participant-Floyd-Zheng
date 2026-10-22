// pop-up for reporting incidents
import { useEffect, useState } from 'react';
import {
    Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle,
    FormControlLabel, MenuItem, Stack, Switch, TextField,
} from '@mui/material';
import { apiErrorMessage } from './EntityCrudGrid.jsx';

// These MUST match the .value strings of Priority / Category / Status in app/models/enums.py
export const PRIORITY_OPTIONS = ['Low', 'Medium', 'High', 'Critical'];
export const CATEGORY_OPTIONS = ['Hardware', 'Software', 'Security', 'Infrastructure', 'Equipment', 'Other'];
export const NEW_INCIDENT_STATUS = 'Open';
export const STATUS_OPTIONS = ['Open', 'Blocked', 'In_Progress', 'Resolved', 'Closed'];
export const RESOLVED_STATUS = 'Resolved';
const INITIAL = { priority: '', category: '', is_escalated: false, incident_notes: '' };

function ReportIncidentDialog({ seat, onClose, onSubmit }) {
    const [values, setValues] = useState(INITIAL);
    const [error, setError] = useState(null);
    const [saving, setSaving] = useState(false);

    // reset the form each time it opens for a seat
    useEffect(() => {
        if (seat) {
            setValues(INITIAL);
            setError(null);
        }
    }, [seat]);

    const set = (field) => (e) =>
        setValues((prev) => ({ ...prev, [field]: field === 'is_escalated' ? e.target.checked : e.target.value }));

    const handleSubmit = async () => {
        setSaving(true);
        setError(null);
        try {
            await onSubmit({
                seat_id: seat.id,          // reported_by is set by the backend from the logged-in user
                status: NEW_INCIDENT_STATUS,
                priority: values.priority,
                category: values.category,
                is_escalated: values.is_escalated,
                incident_notes: values.incident_notes.trim() || null,
            });
        } catch (err) {
            setError(apiErrorMessage(err));
        } finally {
            setSaving(false);
        }
    };

    const location = seat
        ? `${seat.facility_name ?? '?'} / ${seat.building_name ?? '?'} / Floor ${seat.floor_number ?? '?'} / Seat ${seat.seat_number ?? seat.id}`
        : '';

    return (
        <Dialog open={Boolean(seat)} onClose={() => !saving && onClose()}>
            <DialogTitle>Report Incident</DialogTitle>
            <DialogContent>
                <Stack spacing={2} sx={{ mt: 1, minWidth: 380 }}>
                    <Alert severity="info">{location}</Alert>
                    {error && <Alert severity="error">{error}</Alert>}
                    <TextField select required label="Category" value={values.category} onChange={set('category')}>
                        {CATEGORY_OPTIONS.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
                    </TextField>
                    <TextField select required label="Priority" value={values.priority} onChange={set('priority')}>
                        {PRIORITY_OPTIONS.map((p) => <MenuItem key={p} value={p}>{p}</MenuItem>)}
                    </TextField>
                    <TextField
                        label="Notes"
                        multiline
                        minRows={2}
                        value={values.incident_notes}
                        onChange={set('incident_notes')}
                        inputProps={{ maxLength: 120 }}   // incident_notes is String(120)
                        helperText={`${values.incident_notes.length}/120`}
                    />
                    <FormControlLabel
                        control={<Switch checked={values.is_escalated} onChange={set('is_escalated')} />}
                        label="Escalate"
                    />
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={saving}>Cancel</Button>
                <Button
                    variant="contained"
                    color="warning"
                    onClick={handleSubmit}
                    disabled={saving || !values.category || !values.priority}
                >
                    Report
                </Button>
            </DialogActions>
        </Dialog>
    );
}

export default ReportIncidentDialog;
