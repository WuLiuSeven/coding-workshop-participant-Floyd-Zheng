import { AppBar, Toolbar, Typography, Box, Button } from '@mui/material';

function AppHeader({ first_name, role, onLogout, adminMenu }) {
    return (
        <AppBar position="static">
            <Toolbar>
                <Typography variant="h6" component="h1" color="secondary">
                    ACME
                </Typography>
                {adminMenu}
                {first_name && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 3, ml: 'auto' }}>
                        <Typography variant="body2">{first_name} [{role}]</Typography>
                        <Button color="inherit" variant="outlined" onClick={onLogout}>Log Out</Button>
                    </Box>
                )}
            </Toolbar>
        </AppBar>
    );
}

export default AppHeader;