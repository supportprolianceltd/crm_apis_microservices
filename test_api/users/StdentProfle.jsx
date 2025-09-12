import React, { useState, useEffect } from 'react';
import {
  Dialog, DialogTitle, DialogContent, Button, Box, TextField,
  Grid, Avatar, FormControl, InputLabel, Select, MenuItem, Alert,
  Typography, Paper, Divider, Tooltip,
} from '@mui/material';
import { Upload } from '@mui/icons-material';
import { userAPI } from '../../../config';

const accent = '#1976d2';
const bgGradient = 'linear-gradient(135deg, #e3f2fd 0%, #fce4ec 100%)';

const StudentProfile = ({ open, onClose, student, onSave }) => {
  const [formData, setFormData] = useState({
    id: student?.id || '',
    student_id: student?.student_id || '',
    first_name: student?.first_name || '',
    last_name: student?.last_name || '',
    email: student?.email || '',
    phone: student?.phone || '',
    title: student?.title || '',
    language: student?.language || 'en',
  });

  const [profilePicturePreview, setProfilePicturePreview] = useState(student?.profile_picture || '');
  const [profilePictureFile, setProfilePictureFile] = useState(null);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    setFormData({
      id: student?.id || '',
      student_id: student?.student_id || '',
      first_name: student?.first_name || '',
      last_name: student?.last_name || '',
      email: student?.email || '',
      phone: student?.phone || '',
      title: student?.title || '',
      language: student?.language || 'en',
    });
    setProfilePicturePreview(student?.profile_picture || '');
    setProfilePictureFile(null);
  }, [student, open]);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handlePhotoChange = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    setProfilePictureFile(file);
    setProfilePicturePreview(URL.createObjectURL(file));
  };

  const handleSave = async () => {
    setUploading(true);
    setError(null);
    try {
      if (!formData.id) throw new Error('Student ID is missing');

      let data;
      let isMultipart = !!profilePictureFile;
      if (isMultipart) {
        data = new FormData();
        data.append('first_name', formData.first_name);
        data.append('last_name', formData.last_name);
        data.append('email', formData.email);
        data.append('phone', formData.phone);
        data.append('title', formData.title);
        data.append('language', formData.language);
        data.append('profile_picture', profilePictureFile);
      } else {
        data = {
          first_name: formData.first_name,
          last_name: formData.last_name,
          email: formData.email,
          phone: formData.phone,
          title: formData.title,
          language: formData.language,
        };
      }

      await userAPI.updateUser(formData.id, data, isMultipart);
      onSave();
      onClose();
    } catch (err) {
      setError('Failed to update profile. Please try again.');
      console.error('Profile update error:', err);
    } finally {
      setUploading(false);
    }
  };

  if (!student) return null;

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm"
      PaperProps={{
        sx: {
          borderRadius: 4,
          background: bgGradient,
          boxShadow: 8,
          mx: 2,
        }
      }}>
      <DialogTitle sx={{
        background: accent,
        color: '#fff',
        borderTopLeftRadius: 16,
        borderTopRightRadius: 16,
        pb: 2,
        textAlign: 'center'
      }}>
        <Typography variant="h5" fontWeight="bold" letterSpacing={1}>
          Student Profile
        </Typography>
        <Typography variant="subtitle2" color="#e3f2fd">
          Manage your personal information
        </Typography>
      </DialogTitle>
      <DialogContent sx={{ pt: 3 }}>
        {error && (
          <Box sx={{ mb: 2 }}>
            <Alert severity="error">{error}</Alert>
          </Box>
        )}
        <Paper elevation={0} sx={{
          p: { xs: 1.5, sm: 3 },
          borderRadius: 3,
          background: '#fff',
          mb: 2,
          maxWidth: 600,
          mx: 'auto'
        }}>
          <Grid container spacing={3} justifyContent="center">
            <Grid item xs={12} sm={4} display="flex" flexDirection="column" alignItems="center">
              <Avatar
                src={profilePicturePreview}
                sx={{
                  width: 110,
                  height: 110,
                  border: `4px solid ${accent}`,
                  boxShadow: 3,
                  mb: 1,
                }}
              />
              <Tooltip title="Upload a new profile picture" arrow>
                <Button
                  variant="contained"
                  component="label"
                  startIcon={<Upload />}
                  disabled={uploading}
                  sx={{
                    background: accent,
                    color: '#fff',
                    fontWeight: 600,
                    borderRadius: 2,
                    px: 2,
                    fontSize: { xs: 12, sm: 14 },
                    '&:hover': { background: '#1565c0' }
                  }}
                >
                  {uploading ? 'Uploading...' : 'Change Photo'}
                  <input type="file" hidden accept="image/*" onChange={handlePhotoChange} />
                </Button>
              </Tooltip>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1, textAlign: 'center' }}>
                {formData.first_name} {formData.last_name}
              </Typography>
              <Typography variant="caption" color="text.disabled" sx={{ textAlign: 'center' }}>
                {formData.email}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={8}>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Student ID"
                    name="student_id"
                    value={formData.student_id}
                    margin="dense"
                    disabled
                    InputProps={{
                      sx: { background: '#f3f6f9', borderRadius: 2 }
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Email"
                    name="email"
                    value={formData.email}
                    margin="dense"
                    disabled
                    InputProps={{
                      sx: { background: '#f3f6f9', borderRadius: 2 }
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="First Name"
                    name="first_name"
                    value={formData.first_name}
                    onChange={handleChange}
                    margin="dense"
                    InputProps={{
                      sx: { borderRadius: 2 }
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Last Name"
                    name="last_name"
                    value={formData.last_name}
                    onChange={handleChange}
                    margin="dense"
                    InputProps={{
                      sx: { borderRadius: 2 }
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Phone"
                    name="phone"
                    value={formData.phone}
                    onChange={handleChange}
                    margin="dense"
                    InputProps={{
                      sx: { borderRadius: 2 }
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Title"
                    name="title"
                    value={formData.title}
                    onChange={handleChange}
                    margin="dense"
                    InputProps={{
                      sx: { borderRadius: 2 }
                    }}
                  />
                </Grid>
                <Grid item xs={12}>
                  <FormControl fullWidth margin="dense">
                    <InputLabel>Language</InputLabel>
                    <Select
                      name="language"
                      value={formData.language}
                      onChange={handleChange}
                      sx={{ borderRadius: 2, background: '#fafafa' }}
                    >
                      <MenuItem value="en">English</MenuItem>
                      <MenuItem value="es">Spanish</MenuItem>
                      <MenuItem value="fr">French</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </Paper>
        <Divider sx={{ my: 2 }} />
        <Box display="flex" justifyContent="center" gap={2}>
          <Button onClick={onClose} variant="outlined" sx={{
            borderRadius: 2,
            fontWeight: 600,
            color: accent,
            borderColor: accent,
            px: 4,
            '&:hover': { background: '#e3f2fd' }
          }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={uploading}
            sx={{
              borderRadius: 2,
              fontWeight: 600,
              background: accent,
              color: '#fff',
              px: 4,
              boxShadow: 2,
              '&:hover': { background: '#1565c0' }
            }}
          >
            Save Changes
          </Button>
        </Box>
      </DialogContent>
    </Dialog>
  );
};

export default StudentProfile;