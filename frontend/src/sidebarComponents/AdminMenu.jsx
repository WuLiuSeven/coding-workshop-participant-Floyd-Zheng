import { useState } from 'react';
import { Button, Menu, MenuItem } from '@mui/material';

const PAGES = [
    { value: 'locations', label: 'Locations & Incidents' },
    { value: 'users', label: 'Manage Users' },
    { value: 'engineers', label: 'Manage Engineers' },
];

/*
 * Dropdown for the app header. Render it only for Facility Admins;
 * it just reports which page was picked via onSelect.
 */
function AdminMenu({ current, onSelect }) {
    const [anchorEl, setAnchorEl] = useState(null);

    const choose = (value) => {
        setAnchorEl(null);
        onSelect(value);
    };

    return (
        <>
            <Button color="inherit" onClick={(e) => setAnchorEl(e.currentTarget)}>
                Admin ▾
            </Button>
            <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
                {PAGES.map((page) => (
                    <MenuItem key={page.value} selected={page.value === current} onClick={() => choose(page.value)}>
                        {page.label}
                    </MenuItem>
                ))}
            </Menu>
        </>
    );
}

export default AdminMenu;
