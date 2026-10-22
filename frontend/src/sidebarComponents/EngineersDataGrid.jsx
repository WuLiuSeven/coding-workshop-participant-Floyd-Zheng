import { useCallback, useEffect, useMemo, useState } from 'react';
import apiClient from '../api/client.js';
import { Alert, Box, CircularProgress, Typography } from '@mui/material';
import EntityCrudGrid from './EntityCrudGrid.jsx';

// Must match the .value strings of Team in app/models/enums.py
const TEAM_OPTIONS = ['Infrastructure', 'Equipment', 'Security', 'Hardware', 'Software'];

function EngineersDataGrid({ onSuccess }) {
    const [engineers, setEngineers] = useState([]);
    const [users, setUsers] = useState([]);
    const [incidents, setIncidents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchAll = useCallback(async ({ silent = false } = {}) => {
        if (!silent) setLoading(true);
        try {
            const [engineerRes, userRes, incidentRes] = await Promise.all([
                apiClient.get('/engineer'),
                apiClient.get('/auth'),
                apiClient.get('/incident'),
            ]);
            setEngineers(engineerRes.data);
            setUsers(userRes.data);
            setIncidents(incidentRes.data);
            setError(null);
        } catch {
            setError('Could not load engineers');
        } finally {
            if (!silent) setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAll();
    }, [fetchAll]);

    const userById = useMemo(() => new Map(users.map((u) => [u.id, u])), [users]);

    const rows = useMemo(() => engineers.map((e) => {
        const u = userById.get(e.user_id);
        return {
            ...e,
            name: u ? `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() : `User ${e.user_id}`,
            email: u?.email ?? '',
            incident_label: e.at_incident ? `#${e.at_incident}` : '',
        };
    }), [engineers, userById]);

    const columns = useMemo(() => [
        { field: 'id', headerName: 'ID', width: 70 },
        { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
        { field: 'email', headerName: 'Email', flex: 1, minWidth: 220 },
        { field: 'team', headerName: 'Team', width: 130 },
        { field: 'is_available', headerName: 'Available', width: 100, type: 'boolean' },
        { field: 'incident_label', headerName: 'Assigned Incident', width: 150 },
    ], []);

    const fields = useMemo(() => {
        const userOptions = users
            .filter((u) => u.role !== 'Facility_Admin')
            .map((u) => ({ value: u.id, label: `${u.first_name ?? ''} ${u.last_name ?? ''} · ${u.email} (${u.role})` }));

        const incidentOptions = [
            { value: '', label: '— None —' },
            ...incidents.map((i) => ({
                value: i.id,
                label: `#${i.id} · ${i.category} · ${i.status}${i.resolved_at ? ' (resolved)' : ''}`,
            })),
        ];

        return [
            { name: 'user_id', label: 'User', type: 'select', options: userOptions, required: true },
            { name: 'team', label: 'Team', type: 'select', options: TEAM_OPTIONS.map((t) => ({ value: t, label: t })), required: true },
            { name: 'is_available', label: 'Available', type: 'boolean' },
            { name: 'at_incident', label: 'Assigned Incident', type: 'select', options: incidentOptions },
        ];
    }, [users, incidents]);

    const handleCreate = async (payload) => {
        await apiClient.post('/engineer', payload);
        onSuccess?.('Engineer created.');
        await fetchAll({ silent: true });
    };

    const handleUpdate = async (row, payload) => {
        await apiClient.patch(`/engineer/${row.id}`, payload);   // payload has every EngineerBase field
        onSuccess?.(`Engineer ${row.name} updated.`);
        await fetchAll({ silent: true });
    };

    const handleDelete = async (row) => {
        await apiClient.delete(`/engineer/${row.id}`);
        onSuccess?.(`Engineer ${row.name} deleted.`);
        await fetchAll({ silent: true });
    };

    if (loading) return <CircularProgress />;
    if (error) return <Alert severity="error">{error}</Alert>;

    return (
        <Box>
            <Typography variant="h6" sx={{ mb: 2 }}>Engineers</Typography>
            <EntityCrudGrid
                entityLabel="Engineer"
                rows={rows}
                columns={columns}
                fields={fields}
                canManage
                deleteWarning="Engineers who resolved incidents can't be deleted until those incidents are reassigned."
                onCreate={handleCreate}
                onUpdate={handleUpdate}
                onDelete={handleDelete}
            />
        </Box>
    );
}

export default EngineersDataGrid;
