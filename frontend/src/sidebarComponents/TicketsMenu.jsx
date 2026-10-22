import { useState } from 'react';
import { Button, Menu, MenuItem } from '@mui/material';

const PAGES = [
    { value: 'locations', label: 'Locations & Incidents' },
    { value: 'tickets-all', label: 'All Tickets' },
    { value: 'tickets-mine', label: 'My Tickets' },
];

/* Header dropdown shown to every logged-in user. */
function TicketsMenu({ current, onSelect }) {
    const [anchorEl, setAnchorEl] = useState(null);

    const choose = (value) => {
        setAnchorEl(null);
        onSelect(value);
    };

    return (
        <>
            <Button color="inherit" sx={{ ml: 2 }} onClick={(e) => setAnchorEl(e.currentTarget)}>
                Tickets ▾
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

export default TicketsMenu;
