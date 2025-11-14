import api from './axios';

export const taskAPI = {
  getTasks: (params = {}) => {
    // Default to ordering by created_at descending (LIFO - most recent first)
    const defaultParams = { ordering: '-created_at', ...params };
    return api.get('/tasks/', { params: defaultParams });
  },
  getAllTasks: () => api.get('/tasks/'), // Admin can get all tasks
  // API: GET /api/project-manager/api/tasks/?assigned_to_id={userId}
  // Used for user analytics - retrieves all tasks assigned to a specific user
  // See POSTMAN_EXAMPLES.md - "Get Tasks by User (Analytics)" section
  getTasksByUser: (userId) => api.get(`/users/${userId}/tasks/`),
  getMyTasks: () => api.get('/tasks/my_tasks/'),
  getTask: (id) => api.get(`/tasks/${id}/`),
  createTask: (data) => api.post('/tasks/', data),
  updateTask: (id, data) => api.put(`/tasks/${id}/`, data),
  updateTaskStatus: (id, data) => api.patch(`/tasks/${id}/update_status/`, data),
  updateTaskProgress: (id, progress_percentage) => api.patch(`/tasks/${id}/update_status/`, { progress_percentage }),
  deleteTask: (id) => api.delete(`/tasks/${id}/`),
  addComment: (taskId, text) => api.post(`/tasks/${taskId}/comment/`, { text }),
  addReport: (taskId, data) => api.post(`/tasks/${taskId}/report/`, data),
  getAllReports: () => api.get('/reports/'),
  getAllComments: () => api.get('/comments/'),
  bulkCreateTasks: (tasksData) => api.post('/tasks/bulk_create/', { tasks: tasksData }),
};