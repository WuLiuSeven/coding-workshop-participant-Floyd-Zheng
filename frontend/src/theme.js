import {createTheme} from '@mui/material/styles'

const theme = createTheme({
    palette: {
        mode: 'light',
        primary: {
            main: '#003A72'
        },
        //secondary buttons
        secondary: {
            main: '#DB230B'
        },
    },
    shape: {
        borderRadius: 8,
    }
});

export default theme;
