import {useState} from 'react';
import {Alert, Box, Button, Paper, TextField, Typography, Link} from '@mui/material';
import {useAuth} from '../context/AuthContext.jsx';
import RegisterForm from './RegisterForm.jsx';


{/** extracts the login function from global AuthContext */}
function LoginForm(){
    const {login} = useAuth();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [registerOpen, setRegisterOpen] = useState(false);
    


{/** form submission handler function */}
const handleSubmit = async (event) => {
    {/** prevent a full page refresh on submit */}
    event.preventDefault()
    setError(null);
    try{
        await login(email, password);
    } catch (loginError){
        if(loginError.response?.status == 401){
            setError('Incorrect Email or password')
        } else{
            setError('Something went wrong logging in, please try again shortly');
        }
    }
};

return (
    <Box sx={{display: 'flex', justifyConext: 'center', mt: 8}}>
        <Paper component='form' onSubmit={handleSubmit} variant="outlined" sx={{p:4, width: 320}}>
            <Typography variant="h6" gutterBottom>
                ACME Login Center
            </Typography>
            {error && <Alert severity="error" sx={{mb: 2}}>{error}</Alert>}
            {success && <Alert severity="success" sx={{mb: 2}}>{success}</Alert>}
            <TextField
                label="Email"
                fullWidth
                margin="normal"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                />
            <TextField
                label="Password"
                type="password"
                fullWidth
                margin="normal"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                />
                <Button type="submit" variant="contained" fullWidth sx={{mt: 2}}>
                    Log In
                </Button>
                {/** register */}
                <Typography variant="body2" align="center" sx={{mt: 2}}>
                    Don't have an account? Register as a Employee{' '}
                    {/* type="button" so clicking this doesn't submit the login form */}
                    <Link component="button" type="button" onClick={() => setRegisterOpen(true)}>
                        Register
                    </Link>
                </Typography>
        </Paper>

        <RegisterForm
                open={registerOpen}
                onClose={() => setRegisterOpen(false)}
                onSuccess={(message) => {
                    setError(null);
                    setSuccess(message);
                }}
        />
    </Box>
);

} //end of LoginForm()

export default LoginForm;