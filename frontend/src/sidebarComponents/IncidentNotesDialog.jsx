import { useEffect, useState } from 'react';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import {
    Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
    Divider, IconButton, Stack, TextField, Typography,
} from '@mui/material';
import { apiErrorMessage } from './EntityCrudGrid.jsx';

/*
 * Notes thread for one incident.
 * Everyone can read and add; only managers (Facility Admin) can edit or delete,
 * matching PATCH/DELETE /note/{id}.
 */
function IncidentNotesDialog({ incident, notes, textField, maxLength, canManage, onClose, onAdd, onUpdate, onDelete }) {
    const [draft, setDraft] = useState('');
    const [editingId, setEditingId] = useState(null);
    const [editText, setEditText] = useState('');
    const [error, setError] = useState(null);
    const [saving, setSaving] = useState(false);

    // reset whenever the dialog opens for a different incident
    useEffect(() => {
        setDraft('');
        setEditingId(null);
        setError(null);
    }, [incident?.id]);

    // runs an API action, shows its error inside the dialog instead of closing
    const run = async (action) => {
        setSaving(true);
        setError(null);
        try {
            await action();
            return true;
        } catch (err) {
            setError(apiErrorMessage(err));
            return false;
        } finally {
            setSaving(false);
        }
    };

    const handleAdd = async () => {
        if (await run(() => onAdd(draft.trim()))) setDraft('');
    };

    const handleSaveEdit = async (note) => {
        if (await run(() => onUpdate(note, editText.trim()))) setEditingId(null);
    };

    const handleDelete = async (note) => {
        if (!window.confirm('Delete this note?')) return;
        await run(() => onDelete(note));
    };

    return (
        <Dialog open={Boolean(incident)} onClose={() => !saving && onClose()} fullWidth maxWidth="sm">
            <DialogTitle>
                Notes for incident {incident?.id}
                <Typography variant="body2" color="text.secondary">{incident?.location}</Typography>
            </DialogTitle>

            <DialogContent dividers>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                {notes.length === 0 && (
                    <Typography color="text.secondary" sx={{ mb: 2 }}>No notes yet.</Typography>
                )}

                <Stack spacing={1.5} divider={<Divider flexItem />} sx={{ mb: 2 }}>
                    {notes.map((note) => (
                        <Box key={note.id}>
                            {editingId === note.id ? (
                                <Stack spacing={1}>
                                    <TextField
                                        multiline
                                        minRows={2}
                                        value={editText}
                                        onChange={(e) => setEditText(e.target.value)}
                                        inputProps={maxLength ? { maxLength } : undefined}
                                        helperText={maxLength ? `${editText.length}/${maxLength}` : undefined}
                                        autoFocus
                                    />
                                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                                        <Button size="small" onClick={() => setEditingId(null)} disabled={saving}>Cancel</Button>
                                        <Button
                                            size="small"
                                            variant="contained"
                                            onClick={() => handleSaveEdit(note)}
                                            disabled={saving || !editText.trim()}
                                        >
                                            Save
                                        </Button>
                                    </Stack>
                                </Stack>
                            ) : (
                                <Stack direction="row" sx={{ alignItems: 'flex-start' }} spacing={1}>
                                    <Box sx={{ flex: 1 }}>
                                        <Typography sx={{ whiteSpace: 'pre-wrap' }}>{note[textField]}</Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            Note #{note.id}
                                            {note.created_at && ` · ${new Date(note.created_at).toLocaleString()}`}
                                        </Typography>
                                    </Box>
                                    {canManage && (
                                        <>
                                            <IconButton
                                                size="small"
                                                aria-label="Edit note"
                                                onClick={() => { setEditingId(note.id); setEditText(note[textField] ?? ''); }}
                                            >
                                                <EditIcon fontSize="small" />
                                            </IconButton>
                                            <IconButton size="small" aria-label="Delete note" onClick={() => handleDelete(note)}>
                                                <DeleteIcon fontSize="small" />
                                            </IconButton>
                                        </>
                                    )}
                                </Stack>
                            )}
                        </Box>
                    ))}
                </Stack>

                <TextField
                    label="Add a note"
                    multiline
                    minRows={2}
                    fullWidth
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    inputProps={maxLength ? { maxLength } : undefined}
                    helperText={maxLength ? `${draft.length}/${maxLength}` : undefined}
                />
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} disabled={saving}>Close</Button>
                <Button variant="contained" onClick={handleAdd} disabled={saving || !draft.trim()}>
                    Add note
                </Button>
            </DialogActions>
        </Dialog>
    );
}

export default IncidentNotesDialog;
