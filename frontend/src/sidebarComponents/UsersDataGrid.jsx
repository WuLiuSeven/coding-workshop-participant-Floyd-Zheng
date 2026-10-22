import { useCallback, useEffect, useMemo, useState } from 'react';
import apiClient from '../api/client.js';
import UpgradeIcon from '@mui/icons-material/Upgrade';
import { GridActionsCellItem } from '@mui/x-data-grid';
import { Alert, Box, CircularProgress, Typography } from '@mui/material';
import EntityCrudGrid, { apiErrorMessage } from './EntityCrudGrid.jsx';

// Must match the .value strings of Role in app/models/enums.py
const ADMIN_ROLE = 'Facility_Admin';
const ENGINEER_ROLE = 'Engineer';
const EMPLOYEE_ROLE = 'Employee';

// Admins are created in code only, so the form never offers that role
const ROLE_OPTIONS = [
    { value: EMPLOYEE_ROLE, label: EMPLOYEE_ROLE },
    { value: ENGINEER_ROLE, label: ENGINEER_ROLE },
];

const isAdminRow = (row) => row.role === ADMIN_ROLE;

// PATCH /auth/{id} takes the full UserBase, so always send every field
const toUserPayload = (row, overrides = {}) => ({
    email: row.email,
    first_name: row.first_name,
    last_name: row.last_name,
    is_active: row.is_active,
    role: row.role,
    ...overrides,
});

function UsersDataGrid({ onSuccess }) {
    const [users, setUsers] = useState([]);
    const [engineers, setEngineers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [actionError, setActionError] = useState(null);

    const fetchAll = useCallback(async ({ silent = false } = {}) => {
        if (!silent) setLoading(true);
        try {
            const [userRes, engineerRes] = await Promise.all([
                apiClient.get('/auth'),
                apiClient.get('/engineer'),
            ]);
            setUsers(userRes.data);
            setEngineers(engineerRes.data);
            setError(null);
        } catch {
            setError('Could not load users');
        } finally {
            if (!silent) setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAll();
    }, [fetchAll]);

    const rows = useMemo(() => {
        const engineerUserIds = new Set(engineers.map((e) => e.user_id));
        return users.map((u) => ({
            ...u,
            full_name: `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim(),
            has_engineer: engineerUserIds.has(u.id),
        }));
    }, [users, engineers]);

    const columns = useMemo(() => [
        { field: 'id', headerName: 'ID', width: 70 },
        { field: 'email', headerName: 'Email', flex: 1, minWidth: 220 },
        { field: 'full_name', headerName: 'Name', flex: 1, minWidth: 160 },
        { field: 'role', headerName: 'Role', width: 140 },
        { field: 'is_active', headerName: 'Active', width: 90, type: 'boolean' },
        { field: 'has_engineer', headerName: 'Engineer Record', width: 140, type: 'boolean' },
    ], []);

    const fields = useMemo(() => [
        { name: 'email', label: 'Email', type: 'text', required: true },
        { name: 'first_name', label: 'First Name', type: 'text', required: true },
        { name: 'last_name', label: 'Last Name', type: 'text', required: true },
        { name: 'role', label: 'Role', type: 'select', options: ROLE_OPTIONS, required: true },
        { name: 'is_active', label: 'Active', type: 'boolean' },
    ], []);

    const handleUpdate = async (row, payload) => {
        await apiClient.patch(`/auth/${row.id}`, toUserPayload(row, payload));
        const promoted = row.role !== ENGINEER_ROLE && payload.role === ENGINEER_ROLE;
        onSuccess?.(promoted ? `${row.email} promoted to Engineer.` : `User ${row.email} updated.`);
        await fetchAll({ silent: true });
    };

    const handleDelete = async (row) => {
        await apiClient.delete(`/auth/${row.id}`);
        onSuccess?.(`User ${row.email} deleted.`);
        await fetchAll({ silent: true });
    };

    // one-click promotion for employees (the backend also creates their engineer record)
    const handlePromote = useCallback(async (row) => {
        if (!window.confirm(`Promote ${row.email} to Engineer?`)) return;
        try {
            setActionError(null);
            await apiClient.patch(`/auth/${row.id}`, toUserPayload(row, { role: ENGINEER_ROLE }));
            onSuccess?.(`${row.email} promoted to Engineer.`);
            await fetchAll({ silent: true });
        } catch (err) {
            setActionError(`Could not promote ${row.email}: ${apiErrorMessage(err)}`);
        }
    }, [fetchAll, onSuccess]);

    const promoteAction = useCallback((row) => (
        row.role === EMPLOYEE_ROLE
            ? [<GridActionsCellItem key="promote" icon={<UpgradeIcon color="primary" />}
                label="Promote to Engineer" onClick={() => handlePromote(row)} />]
            : []
    ), [handlePromote]);

    if (loading) return <CircularProgress />;
    if (error) return <Alert severity="error">{error}</Alert>;

    return (
        <Box>
            <Typography variant="h6" sx={{ mb: 2 }}>Users</Typography>
            {actionError && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setActionError(null)}>{actionError}</Alert>
            )}
            <EntityCrudGrid
                entityLabel="User"
                rows={rows}
                columns={columns}
                fields={fields}
                canCreate={false}
                canEdit
                canDelete
                canEditRow={(row) => !isAdminRow(row)}
                canDeleteRow={(row) => !isAdminRow(row)}
                extraActions={promoteAction}
                extraActionCount={1}
                deleteWarning="Users who reported incidents or have an engineer record can't be deleted until those are removed."
                onUpdate={handleUpdate}
                onDelete={handleDelete}
            />
        </Box>
    );
}

export default UsersDataGrid;
