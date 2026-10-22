import {useState} from 'react';
import {
    Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, TextField,
} from '@mui/material';
import apiClient from '../api/client.js';


const EMPTY_FORM = {
    first_name: '',
    last_name: '',
    email: '',
    password: '',
    role: 'Employee',
};

// Pop-up registration form.
//   open      - whether the dialog is showing
//   onClose   - called when the dialog should close
//   onSuccess - called with a message after an account is created
function RegisterForm({open, onClose, onSuccess}) {
    const [form, setForm] = useState(EMPTY_FORM);
    const [error, setError] = useState(null);
    const [submitting, setSubmitting] = useState(false);

    // one change handler for every field, keyed by the input's name
    const handleChange = (event) => {
        const {name, value} = event.target;
        setForm((prev) => ({...prev, [name]: value}));
    };

    // reset the form whenever the dialog closes
    const handleClose = () => {
        if (submitting) return; // don't close mid-request
        setForm(EMPTY_FORM);
        setError(null);
        onClose();
    };

    // form submission handler
    const handleSubmit = async (event) => {
        // prevent a full page refresh on submit
        event.preventDefault();
        setError(null);
        setSubmitting(true);

        try {
            const response = await apiClient.post('/auth/registerEmployee', form);
            setForm(EMPTY_FORM);
            onSuccess?.(`Account created for ${response.data.email}`);
            window.location.reload();
            onClose();
        } 
        catch (registerError) {
            const status = registerError.response?.status;
            const detail = registerError.response?.data?.detail;

            if (status === 400 && typeof detail === 'string') {
                setError(detail); // e.g. "Email '...' is already used"
            } 
            else if (status === 401) {
                setError('You must be logged in to register a new user');
            } 
            else if (status === 422) {
                setError('Please check that every field is filled in correctly');
            } 
            else {
                setError('Something went wrong creating the account, please try again shortly');
            }
        } 
        finally {
            setSubmitting(false);
        }
    };

    return (
        <Dialog open={open} onClose={handleClose} fullWidth maxWidth="xs">
            <Box component="form" onSubmit={handleSubmit}>
                <DialogTitle>Create an Account</DialogTitle>

                <DialogContent>
                    {error && <Alert severity="error" sx={{mb: 1}}>{error}</Alert>}

                    <TextField label="First Name" name="first_name" fullWidth margin="normal" required
                        autoFocus value={form.first_name} onChange={handleChange} />
                    <TextField label="Last Name" name="last_name" fullWidth margin="normal" required
                        value={form.last_name} onChange={handleChange} />
                    <TextField label="Email" name="email" type="email" fullWidth margin="normal" required
                        value={form.email} onChange={handleChange} />
                    <TextField label="Password" name="password" type="password" fullWidth margin="normal" required
                        value={form.password} onChange={handleChange} />
                    
                </DialogContent>

                <DialogActions sx={{px: 3, pb: 3}}>
                    <Button onClick={handleClose} disabled={submitting}>Cancel</Button>
                    <Button type="submit" variant="contained" disabled={submitting}>
                        {submitting ? 'Creating...' : 'Register'}
                    </Button>
                </DialogActions>
            </Box>
        </Dialog>
    );
}

export default RegisterForm;
