import {Alert, Snackbar, Box} from '@mui/material'
import {useState} from 'react'

import AppHeader from './layout/AppHeader.jsx'
import LoginForm from './auth/LoginForm.jsx';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import LocationsDataGrid from './sidebarComponents/LocationsDataGrid.jsx';

import AdminMenu from './sidebarComponents/AdminMenu.jsx';
import UsersDataGrid from './sidebarComponents/UsersDataGrid.jsx';
import EngineersDataGrid from './sidebarComponents/EngineersDataGrid.jsx';
import TicketsMenu from './sidebarComponents/TicketsMenu.jsx';
import TicketsPage from './sidebarComponents/TicketsPage.jsx';


function Dashboard(){
    const {user, logout} = useAuth()
    const [notification, setNotification] = useState(null)

    const [view, setView] = useState('locations');
    const isAdmin = user?.role === 'Facility_Admin';

    let page = <LocationsDataGrid onSuccess={setNotification} />;
    if (isAdmin && view === 'users') page = <UsersDataGrid onSuccess={setNotification} />;
    if (isAdmin && view === 'engineers') page = <EngineersDataGrid onSuccess={setNotification} />;
    if (view === 'tickets-all') page = <TicketsPage key="tickets-all" mode="all" onSuccess={setNotification} />;
    if (view === 'tickets-mine') page = <TicketsPage key="tickets-mine" mode="mine" onSuccess={setNotification} />;
    

    return (
        <>
            <AppHeader
                first_name={user?.sub}
                role={user?.role}
                onLogout={logout}
                adminMenu={
                <>
                    <TicketsMenu current={view} onSelect={setView} />
                    {isAdmin && <AdminMenu current={view} onSelect={setView} />}
                </>
                }
            />

            <Box sx={{ p: 3 }}>
                {page}
            </Box>

            <Snackbar
                open={Boolean(notification)}
                autoHideDuration={4000}
                onClose={() => setNotification(null)}>
                    <Alert severity="success" onClose={() => setNotification(null)}>
                        {notification}
                    </Alert>
            </Snackbar>

        </>
    );
}

function AppContent(){
    const {isAuthenticated} = useAuth();
    return isAuthenticated ? <Dashboard/> : <LoginForm/>;
}

function App(){
    return (
        <AuthProvider>
            <AppContent/>
        </AuthProvider>
    )
}

export default App;
