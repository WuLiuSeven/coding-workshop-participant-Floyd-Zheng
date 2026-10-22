import { useCallback, useEffect, useMemo, useState } from 'react';
import apiClient from '../api/client.js';
import ReportProblemIcon from '@mui/icons-material/ReportProblem';
import ListAltIcon from '@mui/icons-material/ListAlt';
import PriorityHighIcon from '@mui/icons-material/PriorityHigh';
import ChatBubbleOutlineIcon from '@mui/icons-material/Comment';
import { GridActionsCellItem } from '@mui/x-data-grid';
import { Alert, Box, Chip, CircularProgress, Tab, Tabs } from '@mui/material';

import { useAuth } from '../context/AuthContext.jsx';
import EntityCrudGrid, { apiErrorMessage } from './EntityCrudGrid.jsx';
import ReportIncidentDialog, {
    CATEGORY_OPTIONS, NEW_INCIDENT_STATUS, PRIORITY_OPTIONS, RESOLVED_STATUS, STATUS_OPTIONS,
} from './ReportIncidentDialog.jsx';
import IncidentNotesDialog from './IncidentNotesDialog.jsx';

// Adjust to match your router prefixes
const API = {
    facilities: '/facility',
    buildings: '/building',
    floors: '/floor',
    seats: '/seat',
    incidents: '/incident',
    myIncidents: '/incident/mine',   // incidents reported by the logged-in user
    notes: '/note',
};

// Must match the Note model / NoteBase schema
const NOTE_INCIDENT_FIELD = 'incident_at';   // foreign key to incidents.id
const NOTE_TEXT_FIELD = 'comments';          // the column holding the note text
const NOTE_MAX_LENGTH = 250;                 // comments is String(250)

// Must match Role.FACILITY_ADMIN's value as returned on the user object
const FACILITY_ADMIN_ROLE = 'Facility_Admin';
const ENGINEER_ROLE = 'Engineer';

// An incident counts as resolved if its status says so or it has a resolved date
const isResolved = (incident) =>
    String(incident.status).toLowerCase() === RESOLVED_STATUS || Boolean(incident.resolved_at);

const toOptions = (values) => values.map((v) => ({ value: v, label: v }));

const EMPTY_DATA = { facilities: [], buildings: [], floors: [], seats: [], incidents: [], myIncidents: [], notes: [] };

function LocationsDataGrid({ onSuccess }) {
    const { user } = useAuth();
    const canManage = user?.role === FACILITY_ADMIN_ROLE;
    // matches the backend: PATCH /incident allows admin + engineer, DELETE allows admin only
    const canEditIncidents = canManage || user?.role === ENGINEER_ROLE;
    const canDeleteIncidents = canManage;

    const [tab, setTab] = useState('seats');
    const [data, setData] = useState(EMPTY_DATA);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [reportSeat, setReportSeat] = useState(null);          // seat row the incident dialog is open for
    const [incidentSeatFilter, setIncidentSeatFilter] = useState(null);
    const [actionError, setActionError] = useState(null);         // errors from row actions like escalate
    const [notesIncidentId, setNotesIncidentId] = useState(null); // incident the notes dialog is open for

    // silent = refresh without unmounting the grids (keeps search text, page, sort)
    const fetchAll = useCallback(async ({ silent = false } = {}) => {
        if (!silent) setLoading(true);
        try {
            const keys = Object.keys(API);
            const responses = await Promise.all(keys.map((k) => apiClient.get(API[k])));
            setData(Object.fromEntries(keys.map((k, i) => [k, responses[i].data])));
            setError(null);
        } catch {
            setError('Could not load location data');
        } finally {
            if (!silent) setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAll();
    }, [fetchAll]);

    // ---- join the hierarchy client-side: Facility -> Building -> Floor -> Seat (-> Incident) ----
    const derived = useMemo(() => {
        const facilityById = new Map(data.facilities.map((f) => [f.id, f]));
        const buildingById = new Map(data.buildings.map((b) => [b.id, b]));

        const incidentCounts = new Map();
        for (const inc of data.incidents) {
            const c = incidentCounts.get(inc.seat_id) ?? { open: 0, total: 0 };
            c.total += 1;
            if (!isResolved(inc)) c.open += 1;
            incidentCounts.set(inc.seat_id, c);
        }

        const buildingRows = data.buildings.map((b) => ({
            ...b,
            facility_name: facilityById.get(b.facility_id)?.name,
            floor_count: data.floors.filter((f) => f.building_id === b.id).length,
        }));

        const floorRows = data.floors.map((f) => {
            const building = buildingById.get(f.building_id);
            return {
                ...f,
                building_name: building?.name,
                facility_name: building && facilityById.get(building.facility_id)?.name,
                seat_count: data.seats.filter((s) => s.floor_id === f.id).length,
            };
        });
        const floorRowById = new Map(floorRows.map((f) => [f.id, f]));

        const seatRows = data.seats.map((s) => {
            const floor = floorRowById.get(s.floor_id);
            const counts = incidentCounts.get(s.id) ?? { open: 0, total: 0 };
            return {
                ...s,
                floor_number: floor?.floor_number,
                building_name: floor?.building_name,
                facility_name: floor?.facility_name,
                open_incidents: counts.open,
                total_incidents: counts.total,
            };
        });
        const seatRowById = new Map(seatRows.map((s) => [s.id, s]));

        const notesByIncident = new Map();
        for (const note of data.notes) {
            const key = note[NOTE_INCIDENT_FIELD];
            if (!notesByIncident.has(key)) notesByIncident.set(key, []);
            notesByIncident.get(key).push(note);
        }

        const incidentRows = data.incidents.map((i) => {
            const seat = seatRowById.get(i.seat_id);
            return {
                ...i,
                note_count: notesByIncident.get(i.id)?.length ?? 0,
                location: seat
                    ? `${seat.facility_name} / ${seat.building_name} / Floor ${seat.floor_number} / Seat ${seat.seat_number ?? seat.id}`
                    : `Seat ${i.seat_id}`,
                created_display: i.created_at ? new Date(i.created_at).toLocaleString() : '',
                state: isResolved(i) ? 'Resolved' : i.acknowledged_at ? 'Acknowledged' : 'New',
            };
        });

        // same joined rows as the Incidents tab, limited to what /incident/mine returned
        const myIncidentIds = new Set(data.myIncidents.map((i) => i.id));
        const myIncidentRows = incidentRows.filter((i) => myIncidentIds.has(i.id));

        const facilityRows = data.facilities.map((f) => ({
            ...f,
            building_count: data.buildings.filter((b) => b.facility_id === f.id).length,
        }));

        return {
            facilityRows, buildingRows, floorRows, seatRows, incidentRows, myIncidentRows, notesByIncident,
            facilityOptions: data.facilities.map((f) => ({ value: f.id, label: f.name })),
            buildingOptions: buildingRows.map((b) => ({ value: b.id, label: `${b.name} (${b.facility_name ?? '?'})` })),
            floorOptions: floorRows.map((f) => ({
                value: f.id,
                label: `${f.facility_name ?? '?'} / ${f.building_name ?? '?'} / Floor ${f.floor_number}`,
            })),
        };
    }, [data]);

    // ---- shared CRUD handlers (EntityCrudGrid shows errors they throw) ----
    const crud = useCallback((path, label) => ({
        onCreate: async (payload) => {
            await apiClient.post(path, payload);
            onSuccess?.(`${label} created.`);
            await fetchAll({ silent: true });
        },
        onUpdate: async (row, payload) => {
            await apiClient.patch(`${path}/${row.id}`, payload);
            onSuccess?.(`${label} ${row.id} updated.`);
            await fetchAll({ silent: true });
        },
        onDelete: async (row) => {
            await apiClient.delete(`${path}/${row.id}`);
            onSuccess?.(`${label} ${row.id} deleted.`);
            await fetchAll({ silent: true });
        },
    }), [fetchAll, onSuccess]);

    const handleReportIncident = async (payload) => {
        await apiClient.post(API.incidents, payload);   // errors are shown inside the dialog
        onSuccess?.(`Incident reported for seat ${reportSeat.seat_number ?? reportSeat.id}.`);
        setReportSeat(null);
        await fetchAll({ silent: true });
    };

    // Seat row actions available to everyone
    const seatActions = useCallback((row) => [
        <GridActionsCellItem
            key="report"
            icon={<ReportProblemIcon color="warning" />}
            label="Report incident"
            onClick={() => setReportSeat(row)}
        />,
        <GridActionsCellItem
            key="view"
            icon={<ListAltIcon />}
            label="View incidents"
            disabled={row.total_incidents === 0}
            onClick={() => {
                setIncidentSeatFilter(row);
                setTab('incidents');
            }}
        />,
    ], []);

    // Anyone can escalate an incident that isn't already escalated or resolved
    const handleEscalate = useCallback(async (row) => {
        if (!window.confirm(`Escalate incident ${row.id}?\n\n${row.location}`)) return;
        try {
            setActionError(null);
            await apiClient.patch(`${API.incidents}/${row.id}/escalate`);
            onSuccess?.(`Incident ${row.id} escalated.`);
            await fetchAll({ silent: true });
        } catch (err) {
            setActionError(`Could not escalate incident ${row.id}: ${apiErrorMessage(err)}`);
        }
    }, [fetchAll, onSuccess]);

    // ---- notes: anyone can add, only Facility Admin can edit/delete (matches /note routes) ----
    const addNote = async (text) => {
        await apiClient.post(API.notes, { [NOTE_INCIDENT_FIELD]: notesIncidentId, [NOTE_TEXT_FIELD]: text });
        onSuccess?.(`Note added to incident ${notesIncidentId}.`);
        await fetchAll({ silent: true });
    };
    const updateNote = async (note, text) => {
        await apiClient.patch(`${API.notes}/${note.id}`, { [NOTE_TEXT_FIELD]: text });
        onSuccess?.(`Note ${note.id} updated.`);
        await fetchAll({ silent: true });
    };
    const deleteNote = async (note) => {
        await apiClient.delete(`${API.notes}/${note.id}`);
        onSuccess?.(`Note ${note.id} deleted.`);
        await fetchAll({ silent: true });
    };

    const incidentActions = useCallback((row) => [
        <GridActionsCellItem
            key="notes"
            icon={<ChatBubbleOutlineIcon />}
            label={`Notes (${row.note_count})`}
            onClick={() => setNotesIncidentId(row.id)}
        />,
        <GridActionsCellItem
            key="escalate"
            icon={<PriorityHighIcon color={row.is_escalated ? 'disabled' : 'error'} />}
            label={row.is_escalated ? 'Already escalated' : 'Escalate'}
            disabled={row.is_escalated || isResolved(row)}
            onClick={() => handleEscalate(row)}
        />,
    ], [handleEscalate]);

    // ---- column definitions (memoised so the grid doesn't reset on every render) ----
    const columns = useMemo(() => ({
        facilities: [
            { field: 'id', headerName: 'ID', width: 70 },
            { field: 'name', headerName: 'Facility', flex: 1, minWidth: 200 },
            { field: 'building_count', headerName: 'Buildings', width: 110, type: 'number' },
        ],
        buildings: [
            { field: 'id', headerName: 'ID', width: 70 },
            { field: 'name', headerName: 'Building', flex: 1, minWidth: 160 },
            { field: 'facility_name', headerName: 'Facility', flex: 1, minWidth: 160 },
            { field: 'floor_count', headerName: 'Floors', width: 90, type: 'number' },
        ],
        floors: [
            { field: 'id', headerName: 'ID', width: 70 },
            { field: 'floor_number', headerName: 'Floor', width: 90, type: 'number' },
            { field: 'building_name', headerName: 'Building', flex: 1, minWidth: 160 },
            { field: 'facility_name', headerName: 'Facility', flex: 1, minWidth: 160 },
            { field: 'seat_count', headerName: 'Seats', width: 90, type: 'number' },
        ],
        seats: [
            { field: 'id', headerName: 'ID', width: 70 },
            { field: 'seat_number', headerName: 'Seat #', width: 90, type: 'number' },
            { field: 'floor_number', headerName: 'Floor', width: 80, type: 'number' },
            { field: 'building_name', headerName: 'Building', flex: 1, minWidth: 150 },
            { field: 'facility_name', headerName: 'Facility', flex: 1, minWidth: 150 },
            {
                field: 'open_incidents', headerName: 'Open Incidents', width: 130, type: 'number',
                renderCell: ({ value }) =>
                    value > 0 ? <Chip size="small" color="warning" label={value} /> : value,
            },
        ],
        incidents: [
            { field: 'id', headerName: 'ID', width: 70 },
            { field: 'location', headerName: 'Location', flex: 1, minWidth: 260 },
            { field: 'category', headerName: 'Category', width: 120 },
            { field: 'priority', headerName: 'Priority', width: 100 },
            { field: 'status', headerName: 'Status', width: 120 },
            { field: 'state', headerName: 'Progress', width: 120 },
            { field: 'is_escalated', headerName: 'Escalated', width: 100, type: 'boolean' },
            { field: 'note_count', headerName: 'Notes', width: 80, type: 'number' },
            { field: 'created_display', headerName: 'Created', width: 180 },
            { field: 'incident_notes', headerName: 'Notes', flex: 1, minWidth: 180 },
        ],
    }), []);

    const fields = useMemo(() => ({
        facilities: [
            { name: 'name', label: 'Name', type: 'text', required: true },
        ],
        buildings: [
            { name: 'name', label: 'Name', type: 'text', required: true },
            { name: 'facility_id', label: 'Facility', type: 'select', options: derived.facilityOptions, required: true },
        ],
        floors: [
            { name: 'floor_number', label: 'Floor Number', type: 'number', required: true },
            { name: 'building_id', label: 'Building', type: 'select', options: derived.buildingOptions, required: true },
        ],
        seats: [
            { name: 'seat_number', label: 'Seat Number', type: 'number' },
            { name: 'floor_id', label: 'Floor', type: 'select', options: derived.floorOptions, required: true },
        ],
        incidents: [
            { name: 'status', label: 'Status', type: 'select', options: toOptions(STATUS_OPTIONS), required: true },
            { name: 'priority', label: 'Priority', type: 'select', options: toOptions(PRIORITY_OPTIONS), required: true },
            { name: 'category', label: 'Category', type: 'select', options: toOptions(CATEGORY_OPTIONS), required: true },
            { name: 'is_escalated', label: 'Escalated', type: 'boolean' },
            { name: 'incident_notes', label: 'Notes', type: 'textarea', maxLength: 120, nullable: true },
        ],
    }), [derived]);

    // Incident edits also stamp acknowledged_at / resolved_at when the status changes
    const incidentCrud = useMemo(() => {
        const base = crud(API.incidents, 'Incident');
        return {
            ...base,
            onUpdate: (row, payload) => {
                const status = String(payload.status).toLowerCase();
                const now = new Date().toISOString();
                const next = { ...payload };
                if (status !== NEW_INCIDENT_STATUS && !row.acknowledged_at) next.acknowledged_at = now;
                if (status === RESOLVED_STATUS && !row.resolved_at) next.resolved_at = now;
                if (status !== RESOLVED_STATUS && row.resolved_at) next.resolved_at = null;   // reopened
                return base.onUpdate(row, next);
            },
        };
    }, [crud]);

    // look the incident up by id so the dialog shows fresh data after each refresh
    const notesIncident = notesIncidentId == null
        ? null
        : derived.incidentRows.find((i) => i.id === notesIncidentId) ?? null;
    const notesForIncident = notesIncident
        ? [...(derived.notesByIncident.get(notesIncident.id) ?? [])].sort((a, b) => a.id - b.id)
        : [];

    const visibleIncidents = incidentSeatFilter
        ? derived.incidentRows.filter((i) => i.seat_id === incidentSeatFilter.id)
        : derived.incidentRows;

    if (loading) return <CircularProgress />;
    if (error) return <Alert severity="error">{error}</Alert>;

    return (
        <Box>
            <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
                <Tab value="seats" label={`Seats (${data.seats.length})`} />
                <Tab value="mine" label={`My Incidents (${derived.myIncidentRows.length})`} />
                <Tab value="floors" label={`Floors (${data.floors.length})`} />
                <Tab value="buildings" label={`Buildings (${data.buildings.length})`} />
                <Tab value="facilities" label={`Facilities (${data.facilities.length})`} />
                <Tab value="incidents" label={`Incidents (${data.incidents.length})`} />
            </Tabs>

            {actionError && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setActionError(null)}>
                    {actionError}
                </Alert>
            )}

            {tab === 'seats' && (
                <EntityCrudGrid
                    entityLabel="Seat"
                    rows={derived.seatRows}
                    columns={columns.seats}
                    fields={fields.seats}
                    canManage={canManage}
                    extraActions={seatActions}
                    deleteWarning="Seats that still have incidents cannot be deleted."
                    {...crud(API.seats, 'Seat')}
                />
            )}

            {tab === 'mine' && (
                <EntityCrudGrid
                    key="mine"
                    entityLabel="Incident"
                    rows={derived.myIncidentRows}
                    columns={columns.incidents}
                    fields={fields.incidents}
                    canCreate={false}
                    canEdit={canEditIncidents}
                    canDelete={canDeleteIncidents}
                    extraActions={incidentActions}
                    extraActionCount={2}
                    deleteWarning="This permanently removes the incident."
                    {...incidentCrud}
                />
            )}

            {tab === 'floors' && (
                <EntityCrudGrid
                    entityLabel="Floor"
                    rows={derived.floorRows}
                    columns={columns.floors}
                    fields={fields.floors}
                    canManage={canManage}
                    deleteWarning="This also deletes every seat on this floor."
                    {...crud(API.floors, 'Floor')}
                />
            )}

            {tab === 'buildings' && (
                <EntityCrudGrid
                    entityLabel="Building"
                    rows={derived.buildingRows}
                    columns={columns.buildings}
                    fields={fields.buildings}
                    canManage={canManage}
                    deleteWarning="This also deletes all of its floors and seats."
                    {...crud(API.buildings, 'Building')}
                />
            )}

            {tab === 'facilities' && (
                <EntityCrudGrid
                    entityLabel="Facility"
                    rows={derived.facilityRows}
                    columns={columns.facilities}
                    fields={fields.facilities}
                    canManage={canManage}
                    deleteWarning="This also deletes all of its buildings, floors and seats."
                    {...crud(API.facilities, 'Facility')}
                />
            )}

            {tab === 'incidents' && (
                <EntityCrudGrid
                    key="incidents"
                    entityLabel="Incident"
                    rows={visibleIncidents}
                    columns={columns.incidents}
                    fields={fields.incidents}
                    canCreate={false}
                    canEdit={canEditIncidents}
                    canDelete={canDeleteIncidents}
                    extraActions={incidentActions}
                    extraActionCount={2}
                    deleteWarning="This permanently removes the incident."
                    {...incidentCrud}
                    toolbarExtra={incidentSeatFilter && (
                        <Chip
                            label={`Seat ${incidentSeatFilter.seat_number ?? incidentSeatFilter.id} — ${incidentSeatFilter.building_name}`}
                            onDelete={() => setIncidentSeatFilter(null)}
                        />
                    )}
                />
            )}

            <IncidentNotesDialog
                incident={notesIncident}
                notes={notesForIncident}
                textField={NOTE_TEXT_FIELD}
                maxLength={NOTE_MAX_LENGTH}
                canManage={canManage}
                onClose={() => setNotesIncidentId(null)}
                onAdd={addNote}
                onUpdate={updateNote}
                onDelete={deleteNote}
            />

            <ReportIncidentDialog
                seat={reportSeat}
                onClose={() => setReportSeat(null)}
                onSubmit={handleReportIncident}
            />
        </Box>
    );
}

export default LocationsDataGrid;
