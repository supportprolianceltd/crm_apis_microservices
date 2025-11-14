import React, { useState } from 'react';
import { taskAPI } from '../api/tasks';

const CommentForm = ({ taskId, onCommentAdded }) => {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;

    setLoading(true);
    try {
      await taskAPI.addComment(taskId, text.trim());
      setText('');
      onCommentAdded();
    } catch (error) {
      console.error('Error adding comment:', error);
      alert('Failed to add comment');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="mb-6">
      <div className="form-group">
        <label className="form-label">Add a comment</label>
        <textarea
          className="form-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type your comment here..."
          rows="3"
          required
        />
      </div>
      <div className="flex justify-end">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || !text.trim()}
        >
          {loading ? 'Posting...' : 'Post Comment'}
        </button>
      </div>
    </form>
  );
};

export default CommentForm;