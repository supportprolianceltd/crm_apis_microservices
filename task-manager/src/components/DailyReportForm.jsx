import React, { useState } from 'react';
import { taskAPI } from '../api/tasks';

const DailyReportForm = ({ task, onClose, onReportAdded }) => {
  const [formData, setFormData] = useState({
    completed_description: '',
    remaining_description: '',
    reason_for_incompletion: '',
    next_action_plan: '',
    status: task.status
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await taskAPI.addReport(task.id, formData);
      onReportAdded();
    } catch (error) {
      console.error('Error creating daily report:', error);
      alert('Failed to create daily report');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '600px' }}>
        <div className="card-header">
          <h2 className="text-xl font-bold">Add Daily Report</h2>
          <button onClick={onClose} className="btn btn-outline">×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Status</label>
            <select
              name="status"
              className="form-select"
              value={formData.status}
              onChange={handleChange}
              required
            >
              <option value="not_started">Not Started</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="blocked">Blocked</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">What was completed today?</label>
            <textarea
              name="completed_description"
              className="form-textarea"
              value={formData.completed_description}
              onChange={handleChange}
              placeholder="Describe what you accomplished today..."
              rows="3"
            />
          </div>

          <div className="form-group">
            <label className="form-label">What remains to be done?</label>
            <textarea
              name="remaining_description"
              className="form-textarea"
              value={formData.remaining_description}
              onChange={handleChange}
              placeholder="Describe what still needs to be completed..."
              rows="3"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Reason for incompletion (if any)</label>
            <textarea
              name="reason_for_incompletion"
              className="form-textarea"
              value={formData.reason_for_incompletion}
              onChange={handleChange}
              placeholder="Explain any blockers or reasons why work wasn't completed..."
              rows="2"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Next action plan</label>
            <textarea
              name="next_action_plan"
              className="form-textarea"
              value={formData.next_action_plan}
              onChange={handleChange}
              placeholder="What are your plans for the next working day?"
              rows="2"
            />
          </div>

          <div className="flex gap-4 mt-6">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
            >
              {loading ? 'Submitting...' : 'Submit Report'}
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={onClose}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DailyReportForm;