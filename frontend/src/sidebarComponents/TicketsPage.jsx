import { useCallback, useEffect, useMemo, useState } from 'react';
import apiClient from '../api/client.js';
import AssignmentIndIcon from '@mui/icons-material/AssignmentInd';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import { GridActionsCellItem } from '@mui/x-data-grid';
import {
    Alert, Box, Button, Card, CardActionArea, Chip, CircularProgress, Dialog, DialogActions,
    DialogContent, DialogTitle, MenuItem, Stack, TextField, Typography,
} from '@mui/material';

import { useAuth } from '../context/AuthContext.jsx';
import EntityCrudGrid, { apiErrorMessage } from './EntityCrudGrid.jsx';
import { RESOLVED_STATUS } from './ReportIncidentDialog.jsx';

const ADMIN_ROLE = 'Facility_Admin';
const ENGINEER_ROLE = 'Engineer';

/*
 * Ticket workflow, derived from the incident:
 *   Reported    (red)    - incident has no tickets
 *   In progress (yellow) - a ticket exists (acknowledged_at = first ticket's created_at)
 *   Completed   (green)  - incident.resolved_at is set
 */

const STAGES = [
    { key: 'reported', label: 'Reported', color: '#d32f2f', description: 'Waiting for an engineer' },
    { key: 'in_progress', label: 'In progress', color: '#f9a825', description: 'Ticket created, engineer assigned' },
    { key: 'completed', label: 'Completed', color: '#2e7d32', description: 'Incident resolved' },
];
const stageInfo = (key) => STAGES.find((s) => s.key === key);

const stageOf = (incident, ticketCount) => {
    if (incident.resolved_at) return 'completed';
    if (ticketCount > 0) return 'in_progress';
    return 'reported';
};

const fmt = (value) => (value ? new Date(value).toLocaleString() : '—');

const EMPTY_DATA = {
    tickets: [], myTickets: [], incidents: [], myIncidents: [],
    seats: [], floors: [], buildings: [], facilities: [], engineers: [], users: [],
};

// ---------- visuals ----------

function WorkflowBar({ stage }) {
    const index = STAGES.findIndex((s) => s.key === stage);
    const { color, label } = STAGES[index];
    return (
        <Stack spacing={0.25} sx={{ width: '100%', py: 0.75 }}>
            <Stack direction="row" spacing={0.5}>
                {STAGES.map((s, i) => (
                    <Box
                        key={s.key}
                        sx={{ flex: 1, height: 8, borderRadius: 1, bgcolor: i <= index ? color : 'action.disabledBackground' }}
                    />
                ))}
            </Stack>
            <Typography variant="caption" sx={{ color, fontWeight: 500, lineHeight: 1.2 }}>{label}</Typography>
        </Stack>
    );
}

function WorkflowOverview({ counts, selected, onSelect }) {
    return (
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} x={{ alignItems:"stretch", mb: 3 }}>
            {STAGES.map((s, i) => (
                <Stack key={s.key} direction="row" sx={{ alignItems: 'center', flex: 1 }}spacing={1}>
                    <Card
                        variant="outlined"
                        sx={{
                            flex: 1,
                            borderLeft: `6px solid ${s.color}`,
                            outline: selected === s.key ? `2px solid ${s.color}` : 'none',
                        }}
                    >
                        <CardActionArea sx={{ p: 2 }} onClick={() => onSelect(selected === s.key ? null : s.key)}>
                            <Typography variant="overline" sx={{ color: s.color }}>Step {i + 1}</Typography>
                            <Typography variant="h6">{s.label}</Typography>
                            <Typography variant="h4" sx={{ fontWeight: 500 }}>{counts[s.key] ?? 0}</Typography>
                            <Typography variant="body2" color="text.secondary">{s.description}</Typography>
                        </CardActionArea>
                    </Card>
                    {i < STAGES.length - 1 && (
                        <Typography variant="h5" color="text.disabled" sx={{ display: { xs: 'none', md: 'block' } }}>→</Typography>
                    )}
                </Stack>
            ))}
        </Stack>
    );
}

function AssignEngineerDialog({ incident, options, onClose, onAssign }) {
    const [engineerId, setEngineerId] = useState('');
    const [error, setError] = useState(null);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setEngineerId('');
        setError(null);
    }, [incident?.id]);

    const handleSubmit = async () => {
        setSaving(true);
        setError(null);
        try {
            await onAssign(engineerId);
        } catch (err) {
            setError(apiErrorMessage(err));
        } finally {
            setSaving(false);
        }
    };

    return (
        <Dialog open={Boolean(incident)} onClose={() => !saving && onClose()}>
            <DialogTitle>Assign engineer to incident {incident?.id}</DialogTitle>
            <DialogContent>
                <Stack spacing={2} sx={{ mt: 1, minWidth: 400 }}>
                    <Alert severity="info">
                        {incident?.location}
                        <br />
                        This creates a ticket and moves the incident to <b>In progress</b>.
                    </Alert>
                    {error && <Alert severity="error">{error}</Alert>}
                    {options.length === 0 ? (
                        <Alert severity="warning">No engineers yet. Add one under Admin → Manage Engineers.</Alert>
                    ) : (
                        <TextField select label="Engineer" value={engineerId} onChange={(e) => setEngineerId(e.target.value)}>
                            {options.map((opt) => (
                                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                            ))}
                        </TextField>
                    )}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={saving}>Cancel</Button>
                <Button variant="contained" onClick={handleSubmit} disabled={saving || engineerId === ''}>
                    Assign &amp; create ticket
                </Button>
            </DialogActions>
        </Dialog>
    );
}

// ---------- page ----------

function TicketsPage({ mode = 'all', onSuccess }) {
    const { user } = useAuth();
    const isAdmin = user?.role === ADMIN_ROLE;
    const isEngineer = user?.role === ENGINEER_ROLE;

    const [data, setData] = useState(EMPTY_DATA);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [actionError, setActionError] = useState(null);
    const [stageFilter, setStageFilter] = useState(null);
    const [assignIncident, setAssignIncident] = useState(null);

    const fetchAll = useCallback(async ({ silent = false } = {}) => {
        if (!silent) setLoading(true);
        try {
            const requests = {
                tickets: '/ticket',
                myTickets: '/ticket/mine',
                incidents: '/incident',
                myIncidents: '/incident/mine',
                seats: '/seat',
                floors: '/floor',
                buildings: '/building',
                facilities: '/facility',
                // engineer and user lists are admin-only endpoints
                ...(isAdmin ? { engineers: '/engineer', users: '/auth' } : {}),
            };
            const keys = Object.keys(requests);
            const responses = await Promise.all(keys.map((k) => apiClient.get(requests[k])));
            setData({ ...EMPTY_DATA, ...Object.fromEntries(keys.map((k, i) => [k, responses[i].data])) });
            setError(null);
        } catch {
            setError('Could not load tickets');
        } finally {
            if (!silent) setLoading(false);
        }
    }, [isAdmin]);

    useEffect(() => {
        fetchAll();
    }, [fetchAll]);

    const derived = useMemo(() => {
        const facilityById = new Map(data.facilities.map((f) => [f.id, f]));
        const buildingById = new Map(data.buildings.map((b) => [b.id, b]));
        const floorById = new Map(data.floors.map((f) => [f.id, f]));
        const seatById = new Map(data.seats.map((s) => [s.id, s]));
        const userById = new Map(data.users.map((u) => [u.id, u]));
        const engineerById = new Map(data.engineers.map((e) => [e.id, e]));

        const seatLocation = (seatId) => {
            const seat = seatById.get(seatId);
            const floor = seat && floorById.get(seat.floor_id);
            const building = floor && buildingById.get(floor.building_id);
            const facility = building && facilityById.get(building.facility_id);
            if (!seat) return `Seat ${seatId}`;
            return `${facility?.name ?? '?'} / ${building?.name ?? '?'} / Floor ${floor?.floor_number ?? '?'} / Seat ${seat.seat_number ?? seat.id}`;
        };

        // admins get names; everyone else sees the engineer id (engineer details are admin-only)
        const engineerLabel = (engineerId) => {
            const eng = engineerById.get(engineerId);
            const u = eng && userById.get(eng.user_id);
            return u ? `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email : `Engineer #${engineerId}`;
        };

        const ticketsByIncident = new Map();
        for (const t of data.tickets) {
            if (!ticketsByIncident.has(t.incident_id)) ticketsByIncident.set(t.incident_id, []);
            ticketsByIncident.get(t.incident_id).push(t);
        }
        for (const list of ticketsByIncident.values()) {
            list.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));   // newest first
        }

        const incidentById = new Map(data.incidents.map((i) => [i.id, i]));
        const myIncidentIds = new Set(data.myIncidents.map((i) => i.id));
        const myTicketIncidentIds = new Set(data.myTickets.map((t) => t.incident_id));

        const source = mode === 'mine'
            ? data.incidents.filter((i) => myIncidentIds.has(i.id) || myTicketIncidentIds.has(i.id))
            : data.incidents;

        const boardRows = source.map((incident) => {
            const tickets = ticketsByIncident.get(incident.id) ?? [];
            const latest = tickets[0];
            const stage = stageOf(incident, tickets.length);
            return {
                id: incident.id,
                stage,
                stage_label: stageInfo(stage).label,
                location: seatLocation(incident.seat_id),
                category: incident.category,
                priority: incident.priority,
                is_escalated: incident.is_escalated,
                engineer_label: latest ? engineerLabel(latest.engineer_id) : 'Unassigned',
                ticket_label: latest ? `#${latest.id}${tickets.length > 1 ? ` (+${tickets.length - 1})` : ''}` : '—',
                reported_display: fmt(incident.created_at),
                assigned_display: fmt(latest?.created_at),
                completed_display: fmt(incident.resolved_at),
                assigned_to_me: myTicketIncidentIds.has(incident.id),
            };
        });

        const counts = boardRows.reduce((acc, r) => ({ ...acc, [r.stage]: (acc[r.stage] ?? 0) + 1 }), {});

        const ticketRows = data.tickets.map((t) => {
            const incident = incidentById.get(t.incident_id);
            return {
                ...t,
                location: incident ? seatLocation(incident.seat_id) : '',
                engineer_label: engineerLabel(t.engineer_id),
                created_display: fmt(t.created_at),
            };
        });

        const engineerOptions = data.engineers
            .map((e) => ({
                value: e.id,
                available: e.is_available,
                label: `${engineerLabel(e.id)} · ${e.team ?? 'no team'} · ${e.is_available ? 'available' : `busy${e.at_incident ? ` on #${e.at_incident}` : ''}`}`,
            }))
            .sort((a, b) => Number(b.available) - Number(a.available));

        const incidentOptions = data.incidents.map((i) => ({ value: i.id, label: `#${i.id} · ${seatLocation(i.seat_id)}` }));

        return { boardRows, counts, ticketRows, engineerOptions, incidentOptions };
    }, [data, mode]);

    // ---- actions ----

    const handleAssign = async (engineerId) => {
        await apiClient.post('/ticket', { engineer_id: engineerId, incident_id: assignIncident.id });
        onSuccess?.(`Ticket created for incident ${assignIncident.id}.`);
        setAssignIncident(null);
        await fetchAll({ silent: true });
    };

    const handleComplete = useCallback(async (row) => {
        if (!window.confirm(`Mark incident ${row.id} as completed?\n\n${row.location}`)) return;
        try {
            setActionError(null);
            await apiClient.patch(`/incident/${row.id}`, {
                status: RESOLVED_STATUS,
                resolved_at: new Date().toISOString(),
            });
            onSuccess?.(`Incident ${row.id} completed.`);
            await fetchAll({ silent: true });
        } catch (err) {
            setActionError(`Could not complete incident ${row.id}: ${apiErrorMessage(err)}`);
        }
    }, [fetchAll, onSuccess]);

    const boardActions = useCallback((row) => {
        const actions = [];
        if (isAdmin && row.stage !== 'completed') {
            actions.push(
                <GridActionsCellItem
                    key="assign"
                    icon={<AssignmentIndIcon color="primary" />}
                    label={row.stage === 'reported' ? 'Assign engineer' : 'Assign another engineer'}
                    onClick={() => setAssignIncident(row)}
                />
            );
        }
        if (row.stage === 'in_progress' && (isAdmin || (isEngineer && row.assigned_to_me))) {
            actions.push(
                <GridActionsCellItem
                    key="complete"
                    icon={<TaskAltIcon color="success" />}
                    label="Mark completed"
                    onClick={() => handleComplete(row)}
                />
            );
        }
        return actions;
    }, [isAdmin, isEngineer, handleComplete]);

    // ---- grid definitions ----

    const boardColumns = useMemo(() => [
        { field: 'id', headerName: 'Incident', width: 85 },
        {
            field: 'stage_label', headerName: 'Progress', width: 170,
            renderCell: ({ row }) => <WorkflowBar stage={row.stage} />,
        },
        { field: 'location', headerName: 'Location', flex: 1, minWidth: 240 },
        { field: 'category', headerName: 'Category', width: 110 },
        { field: 'priority', headerName: 'Priority', width: 90 },
        { field: 'engineer_label', headerName: 'Engineer', width: 160 },
        { field: 'ticket_label', headerName: 'Ticket', width: 90 },
        { field: 'reported_display', headerName: 'Reported', width: 170 },
        { field: 'assigned_display', headerName: 'Assigned', width: 170 },
        { field: 'completed_display', headerName: 'Completed', width: 170 },
    ], []);

    const ticketColumns = useMemo(() => [
        { field: 'id', headerName: 'Ticket', width: 80 },
        { field: 'incident_id', headerName: 'Incident', width: 90 },
        { field: 'location', headerName: 'Location', flex: 1, minWidth: 240 },
        { field: 'engineer_label', headerName: 'Engineer', width: 180 },
        { field: 'created_display', headerName: 'Created', width: 180 },
    ], []);

    const ticketFields = useMemo(() => [
        { name: 'engineer_id', label: 'Engineer', type: 'select', options: derived.engineerOptions, required: true },
        { name: 'incident_id', label: 'Incident', type: 'select', options: derived.incidentOptions, required: true },
    ], [derived]);

    const handleTicketUpdate = async (row, payload) => {
        await apiClient.patch(`/ticket/${row.id}`, payload);
        onSuccess?.(`Ticket ${row.id} updated.`);
        await fetchAll({ silent: true });
    };

    const handleTicketDelete = async (row) => {
        await apiClient.delete(`/ticket/${row.id}`);
        onSuccess?.(`Ticket ${row.id} deleted.`);
        await fetchAll({ silent: true });
    };

    if (loading) return <CircularProgress />;
    if (error) return <Alert severity="error">{error}</Alert>;

    const visibleRows = stageFilter
        ? derived.boardRows.filter((r) => r.stage === stageFilter)
        : derived.boardRows;

    const subtitle = mode === 'all'
        ? 'Every incident and where it is in the ticket workflow.'
        : isEngineer
            ? 'Incidents you are assigned to, plus any you reported.'
            : 'Incidents you reported and how they are progressing.';

    return (
        <Box>
            <Typography variant="h6">{mode === 'mine' ? 'My Tickets' : 'All Tickets'}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{subtitle}</Typography>

            {actionError && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setActionError(null)}>{actionError}</Alert>
            )}

            <WorkflowOverview counts={derived.counts} selected={stageFilter} onSelect={setStageFilter} />

            <EntityCrudGrid
                entityLabel="Ticket"
                rows={visibleRows}
                columns={boardColumns}
                extraActions={boardActions}
                extraActionCount={2}
                toolbarExtra={stageFilter && (
                    <Chip label={`Showing: ${stageInfo(stageFilter).label}`} onDelete={() => setStageFilter(null)} />
                )}
            />

            {isAdmin && mode === 'all' && (
                <Box sx={{ mt: 4 }}>
                    <Typography variant="h6">Ticket Records</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Reassign or remove individual tickets. New tickets are created by assigning an engineer above.
                    </Typography>
                    <EntityCrudGrid
                        entityLabel="Ticket Record"
                        rows={derived.ticketRows}
                        columns={ticketColumns}
                        fields={ticketFields}
                        canCreate={false}
                        canEdit
                        canDelete
                        deleteWarning="If this is the incident's only ticket, the incident goes back to Reported."
                        onUpdate={handleTicketUpdate}
                        onDelete={handleTicketDelete}
                    />
                </Box>
            )}

            <AssignEngineerDialog
                incident={assignIncident}
                options={derived.engineerOptions}
                onClose={() => setAssignIncident(null)}
                onAssign={handleAssign}
            />
        </Box>
    );
}

export default TicketsPage;
