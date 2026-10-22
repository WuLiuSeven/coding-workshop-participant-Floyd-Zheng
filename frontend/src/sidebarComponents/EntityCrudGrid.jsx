import { useMemo, useState } from 'react';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { DataGrid, GridActionsCellItem } from '@mui/x-data-grid';
import {
    Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
    FormControlLabel, MenuItem, Stack, Switch, TextField,
} from '@mui/material';

/*
 * Generic searchable grid with optional add / edit / delete.
 *
 * fields: form fields for the create/edit dialog, e.g.
 *   { name: 'facility_id', label: 'Facility', type: 'select', options: [{ value, label }], required: true }
 *   type: 'text' | 'textarea' | 'number' | 'select' | 'boolean'
 *   optional: maxLength (text/textarea), nullable (empty text is sent as null)
 */

const emptyValue = (f) => (f.type === 'boolean' ? false : '');

function emptyValues(fields) {
    return Object.fromEntries(fields.map((f) => [f.name, emptyValue(f)]));
}

function toPayload(fields, values) {
    const payload = {};
    for (const f of fields) {
        const raw = values[f.name];
        if (f.type === 'boolean') {
            payload[f.name] = Boolean(raw);
        } else if (f.type === 'number') {
            payload[f.name] = raw === '' || raw == null ? null : Number(raw);
        } else if (f.type === 'select') {
            // keeps the option's own type: numbers for foreign keys, strings for enums
            payload[f.name] = raw === '' || raw == null ? null : raw;
        } else {
            const text = typeof raw === 'string' ? raw.trim() : raw;
            payload[f.name] = f.nullable && text === '' ? null : text;
        }
    }
    return payload;
}

export function apiErrorMessage(error) {
    const detail = error?.response?.data?.detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ');
    return detail ?? 'Request failed';
}

function EntityCrudGrid({
    entityLabel,          // "Building", "Seat", ...
    rows,
    columns,              // data columns (no actions column)
    fields = [],
    canManage = false,    // shorthand: allows Add, Edit and Delete
    canCreate = canManage,
    canEdit = canManage,
    canDelete = canManage,
    canEditRow = () => true,     // per-row override, e.g. protect admin accounts
    canDeleteRow = () => true,
    onCreate,
    onUpdate,
    onDelete,
    extraActions,         // (row) => [<GridActionsCellItem .../>]  shown to everyone
    extraActionCount = 2, // how many icons extraActions returns (sizes the column)
    deleteWarning,
    toolbarExtra,         // extra JSX next to the search box (e.g. a filter chip)
}) {
    const [search, setSearch] = useState('');
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingRow, setEditingRow] = useState(null);
    const [formValues, setFormValues] = useState(() => emptyValues(fields));
    const [formError, setFormError] = useState(null);
    const [gridError, setGridError] = useState(null);
    const [saving, setSaving] = useState(false);

    const filteredRows = useMemo(() => {
        const term = search.trim().toLowerCase();
        if (!term) return rows;
        return rows.filter((row) =>
            columns.some((col) => String(row[col.field] ?? '').toLowerCase().includes(term))
        );
    }, [rows, columns, search]);

    const openCreate = () => {
        setEditingRow(null);
        setFormValues(emptyValues(fields));
        setFormError(null);
        setDialogOpen(true);
    };

    const openEdit = (row) => {
        setEditingRow(row);
        setFormValues(Object.fromEntries(fields.map((f) => [f.name, row[f.name] ?? emptyValue(f)])));
        setFormError(null);
        setDialogOpen(true);
    };

    const handleDelete = async (row) => {
        const message = `Delete ${entityLabel.toLowerCase()} ${row.id}?` +
            (deleteWarning ? `\n\n${deleteWarning}` : '');
        if (!window.confirm(message)) return;
        try {
            setGridError(null);
            await onDelete(row);
        } catch (error) {
            setGridError(`Could not delete ${entityLabel.toLowerCase()}: ${apiErrorMessage(error)}`);
        }
    };

    const missingRequired = fields.some(
        (f) => f.required && (formValues[f.name] === '' || formValues[f.name] == null)
    );

    const handleSubmit = async () => {
        setSaving(true);
        setFormError(null);
        try {
            const payload = toPayload(fields, formValues);
            if (editingRow) await onUpdate(editingRow, payload);
            else await onCreate(payload);
            setDialogOpen(false);
        } catch (error) {
            setFormError(apiErrorMessage(error));
        } finally {
            setSaving(false);
        }
    };

    const allColumns = useMemo(() => {
        const iconCount = (extraActions ? extraActionCount : 0) + (canEdit ? 1 : 0) + (canDelete ? 1 : 0);
        if (iconCount === 0) return columns;
        return [
            {
                field: 'actions',
                type: 'actions',
                headerName: 'Actions',
                width: Math.max(90, 30 + iconCount * 36),
                getActions: (params) => [
                    ...(extraActions ? extraActions(params.row) : []),
                    ...(canEdit && canEditRow(params.row)
                        ? [<GridActionsCellItem key="edit" icon={<EditIcon />} label="Edit"
                            onClick={() => openEdit(params.row)} />]
                        : []),
                    ...(canDelete && canDeleteRow(params.row)
                        ? [<GridActionsCellItem key="delete" icon={<DeleteIcon />} label="Delete"
                            onClick={() => handleDelete(params.row)} />]
                        : []),
                ],
            },
            ...columns,
        ];
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [columns, canEdit, canDelete, canEditRow, canDeleteRow, extraActions, extraActionCount, fields]);

    return (
        <Box>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mb: 2}}>
                {canCreate && fields.length > 0 && (
                    <Button variant="outlined" onClick={openCreate}>Add {entityLabel}</Button>
                )}
                <TextField
                    label={`Search ${entityLabel}s`}
                    size="small"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    sx={{ width: 400 }}
                />
                {toolbarExtra}
            </Stack>

            {gridError && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setGridError(null)}>
                    {gridError}
                </Alert>
            )}

            <Box sx={{ height: 500, width: '100%' }}>
                <DataGrid
                    rows={filteredRows}
                    columns={allColumns}
                    getRowId={(row) => row.id}
                    initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
                    pageSizeOptions={[10, 25, 50, 100]}
                />
            </Box>

            <Dialog open={dialogOpen} onClose={() => !saving && setDialogOpen(false)}>
                <DialogTitle>{editingRow ? `Edit ${entityLabel} ${editingRow.id}` : `Add ${entityLabel}`}</DialogTitle>
                <DialogContent>
                    <Stack spacing={2} sx={{ mt: 1, minWidth: 360 }}>
                        {formError && <Alert severity="error">{formError}</Alert>}
                        {fields.map((f) => f.type === 'boolean' ? (
                            <FormControlLabel
                                key={f.name}
                                label={f.label}
                                control={
                                    <Switch
                                        checked={Boolean(formValues[f.name])}
                                        onChange={(e) => setFormValues((prev) => ({ ...prev, [f.name]: e.target.checked }))}
                                    />
                                }
                            />
                        ) : (
                            <TextField
                                key={f.name}
                                label={f.label}
                                type={f.type === 'number' ? 'number' : 'text'}
                                select={f.type === 'select'}
                                multiline={f.type === 'textarea'}
                                minRows={f.type === 'textarea' ? 2 : undefined}
                                required={f.required}
                                value={formValues[f.name]}
                                inputProps={f.maxLength ? { maxLength: f.maxLength } : undefined}
                                helperText={f.maxLength ? `${String(formValues[f.name] ?? '').length}/${f.maxLength}` : undefined}
                                onChange={(e) => setFormValues((prev) => ({ ...prev, [f.name]: e.target.value }))}
                            >
                                {f.type === 'select' && f.options.map((opt) => (
                                    <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                                ))}
                            </TextField>
                        ))}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogOpen(false)} disabled={saving}>Cancel</Button>
                    <Button variant="contained" onClick={handleSubmit} disabled={saving || missingRequired}>
                        {editingRow ? 'Update' : 'Create'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}

export default EntityCrudGrid;
