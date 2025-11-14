import React, { useState, useEffect } from 'react';
import { Search, Plus, Filter, Calendar, Clock, TrendingUp, CheckCircle2, AlertCircle, PlayCircle, X, Send, BarChart3, MessageSquare, FileText, Edit, LogOut } from 'lucide-react';
import { taskAPI } from '../api/tasks';
import authAPI from '../api/auth';
import Pagination from './Pagination';

// Dashboard Component
const Dashboard = ({ user, onLogout }) => {
  const [tasks, setTasks] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [view, setView] = useState('my-tasks');
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [taskToEdit, setTaskToEdit] = useState(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [stats, setStats] = useState({
    total: 0,
    completed: 0,
    inProgress: 0,
    overdue: 0
  });

  // Default user data if not provided
  const currentUser = user || {
    first_name: 'John',
    last_name: 'Doe',
    email: 'john.doe@company.com',
    username: 'johndoe',
    id: 1
  };

  useEffect(() => {
    loadTasks();
  }, [view]);

  const loadTasks = async () => {
    try {
      setLoading(true);
      const response = await taskAPI.getMyTasks();
      setTasks(response.data);
      calculateStats(response.data);
    } catch (error) {
      console.error('Error loading tasks:', error);
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = (tasks) => {
    const today = new Date();
    const stats = {
      total: tasks.length,
      completed: tasks.filter(task => task.status === 'completed').length,
      inProgress: tasks.filter(task => task.status === 'in_progress').length,
      overdue: tasks.filter(task => {
        if (!task.due_date || task.status === 'completed') return false;
        return new Date(task.due_date) < today;
      }).length
    };
    setStats(stats);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-600 font-medium">Loading tasks...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-xl border-b border-slate-200/60 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                <BarChart3 className="w-6 h-6 text-white" />
              </div>
              <div className="hidden sm:block">
                <h1 className="text-xl font-bold bg-gradient-to-r from-slate-900 to-slate-700 bg-clip-text text-transparent">TaskFlow</h1>
                <p className="text-xs text-slate-500">Project Management</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* User Profile Section - Desktop */}
              <div className="hidden sm:flex items-center gap-3 px-3 py-2 bg-slate-50 rounded-lg border border-slate-200">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                  {currentUser.first_name[0]}{currentUser.last_name[0]}
                </div>
                <div className="hidden md:block">
                  <p className="text-sm font-semibold text-slate-900">{currentUser.first_name} {currentUser.last_name}</p>
                  <p className="text-xs text-slate-500">{currentUser.email}</p>
                </div>
              </div>

              {/* User Profile Section - Mobile */}
              <div className="sm:hidden flex items-center gap-2">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                  {currentUser.first_name[0]}{currentUser.last_name[0]}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:shadow-lg hover:scale-105 transition-all duration-200 font-medium text-sm"
                >
                  <Plus className="w-4 h-4" />
                  <span className="hidden sm:inline">New Task</span>
                </button>

                <button
                  onClick={onLogout}
                  className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-all duration-200 font-medium text-sm"
                >
                  <LogOut className="w-4 h-4" />
                  <span className="hidden sm:inline">Logout</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 lg:gap-6 mb-6 lg:mb-8">
          <StatCard
            title="Total"
            value={stats.total}
            icon={<FileText className="w-5 h-5" />}
            gradient="from-blue-500 to-blue-600"
            bgGradient="from-blue-50 to-blue-100"
          />
          <StatCard
            title="In Progress"
            value={stats.inProgress}
            icon={<PlayCircle className="w-5 h-5" />}
            gradient="from-amber-500 to-orange-600"
            bgGradient="from-amber-50 to-orange-100"
          />
          <StatCard
            title="Completed"
            value={stats.completed}
            icon={<CheckCircle2 className="w-5 h-5" />}
            gradient="from-emerald-500 to-green-600"
            bgGradient="from-emerald-50 to-green-100"
          />
          <StatCard
            title="Overdue"
            value={stats.overdue}
            icon={<AlertCircle className="w-5 h-5" />}
            gradient="from-rose-500 to-red-600"
            bgGradient="from-rose-50 to-red-100"
          />
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
          <div className="lg:col-span-2">
            <TaskList
              tasks={tasks}
              currentUser={currentUser}
              onTaskSelect={setSelectedTask}
              selectedTask={selectedTask}
              onTaskUpdate={loadTasks}
              onTasksChange={setTasks}
            />
          </div>
          
          <div className="lg:col-span-1">
            {selectedTask ? (
              <TaskDetail
                task={selectedTask}
                currentUser={currentUser}
                onTaskUpdate={loadTasks}
                onEditTask={(task) => {
                  setTaskToEdit(task);
                  setShowEditModal(true);
                }}
                onClose={() => setSelectedTask(null)}
              />
            ) : (
              <div className="bg-white rounded-2xl border border-slate-200 p-8 lg:p-12 text-center shadow-sm lg:sticky lg:top-24">
                <div className="w-20 h-20 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <FileText className="w-10 h-10 text-blue-600" />
                </div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">Select a Task</h3>
                <p className="text-sm text-slate-500">Choose a task to view details and manage progress</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {showCreateModal && (
        <CreateTaskModal
          onClose={() => setShowCreateModal(false)}
          onTaskCreated={() => {
            setShowCreateModal(false);
            loadTasks();
          }}
        />
      )}

      {showEditModal && taskToEdit && (
        <EditTaskModal
          task={taskToEdit}
          currentUser={currentUser}
          onClose={() => {
            setShowEditModal(false);
            setTaskToEdit(null);
          }}
          onTaskUpdated={() => {
            setShowEditModal(false);
            setTaskToEdit(null);
            loadTasks();
          }}
        />
      )}
    </div>
  );
};

// Stat Card Component
const StatCard = ({ title, value, icon, gradient, bgGradient }) => {
  return (
    <div className="bg-white rounded-xl lg:rounded-2xl border border-slate-200 p-4 lg:p-6 shadow-sm hover:shadow-md transition-all duration-300 group">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-xs lg:text-sm font-medium text-slate-600 mb-1 lg:mb-2">{title}</p>
          <p className="text-2xl lg:text-3xl font-bold text-slate-900">{value}</p>
        </div>
        <div className={`w-10 h-10 lg:w-12 lg:h-12 rounded-xl bg-gradient-to-br ${bgGradient} flex items-center justify-center group-hover:scale-110 transition-transform duration-300`}>
          <div className={`bg-gradient-to-br ${gradient} bg-clip-text text-transparent`}>
            {icon}
          </div>
        </div>
      </div>
    </div>
  );
};

// Task List Component
const TaskList = ({ tasks, onTaskSelect, selectedTask, onTaskUpdate, onTasksChange, currentUser }) => {
  const [filter, setFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('created_at');

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [paginatedTasks, setPaginatedTasks] = useState([]);
  const [loading, setLoading] = useState(false);

  // Load paginated tasks
  const loadTasks = async (page = 1, statusFilter = filter, search = searchTerm) => {
    setLoading(true);
    try {
      const response = await taskAPI.getMyTasks();

      // For now, implement client-side pagination since my_tasks doesn't support query params
      let filteredTasks = response.data;

      // Apply filters
      if (statusFilter !== 'all') {
        if (statusFilter === 'my_created') {
          filteredTasks = filteredTasks.filter(task => task.assigned_by_id === currentUser.id);
        } else {
          filteredTasks = filteredTasks.filter(task => task.status === statusFilter);
        }
      }

      // Apply search
      if (search.trim()) {
        filteredTasks = filteredTasks.filter(task =>
          task.title.toLowerCase().includes(search.trim().toLowerCase()) ||
          task.description.toLowerCase().includes(search.trim().toLowerCase())
        );
      }

      // Update parent state
      onTasksChange(filteredTasks);

      // Calculate pagination
      const pageSize = 20;
      const totalItems = filteredTasks.length;
      const totalPages = Math.ceil(totalItems / pageSize);
      const startIndex = (page - 1) * pageSize;
      const endIndex = startIndex + pageSize;
      const paginatedItems = filteredTasks.slice(startIndex, endIndex);

      setPaginatedTasks(paginatedItems);
      setTotalItems(totalItems);
      setTotalPages(totalPages);
      setCurrentPage(page);

    } catch (error) {
      console.error('Error loading tasks:', error);
      setPaginatedTasks([]);
      setTotalItems(0);
      setTotalPages(1);
    } finally {
      setLoading(false);
    }
  };

  // Load tasks on mount and when filters change
  useEffect(() => {
    loadTasks(1, filter, searchTerm);
  }, [filter, searchTerm]);

  const handlePageChange = (page) => {
    loadTasks(page, filter, searchTerm);
  };

  const handleFilterChange = (newFilter) => {
    setFilter(newFilter);
    setCurrentPage(1);
  };

  const handleSearchChange = (newSearch) => {
    setSearchTerm(newSearch);
    setCurrentPage(1);
  };

  const statusCounts = {
    all: tasks.length,
    my_created: tasks.filter(t => t.assigned_by_id === currentUser.id).length,
    not_started: tasks.filter(t => t.status === 'not_started').length,
    in_progress: tasks.filter(t => t.status === 'in_progress').length,
    completed: tasks.filter(t => t.status === 'completed').length,
    blocked: tasks.filter(t => t.status === 'blocked').length,
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-4 lg:p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
          <div>
            <h2 className="text-lg lg:text-xl font-bold text-slate-900">Tasks</h2>
            <p className="text-sm text-slate-500 mt-1">{totalItems} total tasks</p>
          </div>
          
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search tasks..."
              className="w-full pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={searchTerm}
              onChange={(e) => handleSearchChange(e.target.value)}
            />
          </div>
        </div>

        {/* Status Filters */}
        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
          {[
            { key: 'all', label: 'All', count: statusCounts.all },
            { key: 'my_created', label: 'My Created', count: statusCounts.my_created },
            { key: 'not_started', label: 'Not Started', count: statusCounts.not_started },
            { key: 'in_progress', label: 'In Progress', count: statusCounts.in_progress },
            { key: 'completed', label: 'Completed', count: statusCounts.completed },
            { key: 'blocked', label: 'Blocked', count: statusCounts.blocked },
          ].map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => handleFilterChange(key)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                filter === key
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {label}
              <span className={`px-1.5 py-0.5 rounded-full text-xs ${
                filter === key ? 'bg-white/20' : 'bg-white'
              }`}>
                {count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Task List */}
      <div className="divide-y divide-slate-200 max-h-[600px] overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
              <p className="text-slate-600">Loading tasks...</p>
            </div>
          </div>
        ) : paginatedTasks.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Search className="w-8 h-8 text-slate-400" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 mb-2">No tasks found</h3>
            <p className="text-slate-500">Try adjusting your filters or search term</p>
          </div>
        ) : (
          paginatedTasks.map(task => (
            <TaskCard
              key={task.id}
              task={task}
              isSelected={selectedTask?.id === task.id}
              onSelect={() => onTaskSelect(task)}
              onUpdate={onTaskUpdate}
            />
          ))
        )}
      </div>

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          totalItems={totalItems}
          pageSize={20}
          onPageChange={handlePageChange}
        />
      )}
    </div>
  );
};

// Task Card Component
const TaskCard = ({ task, isSelected, onSelect }) => {
  const getDaysRemaining = (dueDate) => {
    if (!dueDate) return null;
    const today = new Date();
    const due = new Date(dueDate);
    const diffTime = due - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const daysRemaining = getDaysRemaining(task.due_date);

  const statusConfig = {
    not_started: { color: 'text-slate-700', bg: 'bg-slate-100', label: 'Not Started' },
    in_progress: { color: 'text-blue-700', bg: 'bg-blue-100', label: 'In Progress' },
    completed: { color: 'text-green-700', bg: 'bg-green-100', label: 'Completed' },
    blocked: { color: 'text-amber-700', bg: 'bg-amber-100', label: 'Blocked' }
  };

  const priorityConfig = {
    low: { color: 'text-emerald-700', bg: 'bg-emerald-100', icon: '●' },
    medium: { color: 'text-amber-700', bg: 'bg-amber-100', icon: '●●' },
    high: { color: 'text-rose-700', bg: 'bg-rose-100', icon: '●●●' }
  };

  return (
    <div
      onClick={onSelect}
      className={`p-4 lg:p-6 cursor-pointer transition-all hover:bg-slate-50 ${
        isSelected ? 'bg-blue-50 border-l-4 border-l-blue-600' : ''
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 mb-2">
            <h3 className="font-semibold text-slate-900 line-clamp-2 flex-1">{task.title}</h3>
            <div className="flex gap-2 flex-shrink-0">
              <span className={`px-2 py-1 rounded-lg text-xs font-medium ${statusConfig[task.status].bg} ${statusConfig[task.status].color}`}>
                {statusConfig[task.status].label}
              </span>
              <span className={`px-2 py-1 rounded-lg text-xs font-medium ${priorityConfig[task.priority].bg} ${priorityConfig[task.priority].color}`}>
                {priorityConfig[task.priority].icon}
              </span>
            </div>
          </div>

          {task.description && (
            <p className="text-sm text-slate-600 line-clamp-2 mb-3">{task.description}</p>
          )}

          {task.progress_percentage > 0 && (
            <div className="mb-3">
              <div className="flex items-center justify-between text-xs text-slate-600 mb-1">
                <span>Progress</span>
                <span className="font-semibold">{task.progress_percentage}%</span>
              </div>
              <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all"
                  style={{ width: `${task.progress_percentage}%` }}
                />
              </div>
            </div>
          )}

          <div className="flex items-center gap-4 text-xs text-slate-500 flex-wrap">
            <div className="flex items-center gap-1.5">
              <div className="w-6 h-6 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-full flex items-center justify-center text-white text-xs font-medium">
                {task.assigned_to_first_name[0]}{task.assigned_to_last_name[0]}
              </div>
              <span>{task.assigned_to_first_name} {task.assigned_to_last_name}</span>
            </div>
            
            {task.due_date && (
              <div className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5" />
                <span>{new Date(task.due_date).toLocaleDateString()}</span>
                {daysRemaining !== null && daysRemaining < 0 && (
                  <span className="text-rose-600 font-medium">({Math.abs(daysRemaining)}d overdue)</span>
                )}
              </div>
            )}

            {(task.comments?.length > 0 || task.daily_reports?.length > 0) && (
              <div className="flex items-center gap-3">
                {task.comments?.length > 0 && (
                  <div className="flex items-center gap-1">
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>{task.comments.length}</span>
                  </div>
                )}
                {task.daily_reports?.length > 0 && (
                  <div className="flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" />
                    <span>{task.daily_reports.length}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Task Detail Component
const TaskDetail = ({ task, currentUser, onTaskUpdate, onEditTask, onClose }) => {
  const [activeTab, setActiveTab] = useState('details');
  const [showReportForm, setShowReportForm] = useState(false);
  const [showCommentForm, setShowCommentForm] = useState(false);
  const [updatingProgress, setUpdatingProgress] = useState(false);

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const handleProgressUpdate = async (newProgress) => {
    if (updatingProgress) return;

    setUpdatingProgress(true);
    try {
      await taskAPI.updateTaskProgress(task.id, newProgress);
      // Update local task state
      const updatedTask = { ...task, progress_percentage: newProgress };
      // Trigger parent update
      onTaskUpdate();
    } catch (error) {
      console.error('Error updating progress:', error);
    } finally {
      setUpdatingProgress(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm lg:sticky lg:top-24 overflow-hidden">
      {/* Header */}
      <div className="p-4 lg:p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
        <div className="flex items-start justify-between mb-3">
          <h2 className="text-lg font-bold text-slate-900">Task Details</h2>
          <button
            onClick={onClose}
            className="lg:hidden p-1 hover:bg-slate-200 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowReportForm(true)}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:shadow-lg transition-all font-medium text-sm"
          >
            <Plus className="w-4 h-4" />
            Add Daily Report
          </button>
          {task.assigned_by_id === currentUser.id && (
            <button
              onClick={() => onEditTask(task)}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 transition-all font-medium text-sm"
            >
              <Edit className="w-4 h-4" />
              Edit Task
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 bg-slate-50">
        {['details', 'comments', 'reports'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 px-4 py-3 text-sm font-medium capitalize transition-colors ${
              activeTab === tab
                ? 'text-blue-600 border-b-2 border-blue-600 bg-white'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {tab}
            {tab === 'comments' && task.comments?.length > 0 && ` (${task.comments.length})`}
            {tab === 'reports' && task.daily_reports?.length > 0 && ` (${task.daily_reports.length})`}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-4 lg:p-6 max-h-[500px] overflow-y-auto">
        {activeTab === 'details' && (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 mb-2">Description</h3>
              <p className="text-sm text-slate-600 whitespace-pre-wrap">{task.description}</p>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-900 mb-2">Progress</h3>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full"
                      style={{ width: `${task.progress_percentage}%` }}
                    />
                  </div>
                  <span className="text-sm font-semibold text-slate-900">{task.progress_percentage}%</span>
                </div>

                {/* Progress Slider - Only show if user can edit */}
                {task.assigned_to_id === currentUser.id && (
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-slate-600">Update Progress</label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={task.progress_percentage}
                      onChange={(e) => handleProgressUpdate(parseInt(e.target.value))}
                      disabled={updatingProgress}
                      className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer slider"
                    />
                    <div className="flex justify-between text-xs text-slate-500">
                      <span>0%</span>
                      <span>50%</span>
                      <span>100%</span>
                    </div>
                    {updatingProgress && (
                      <div className="text-xs text-blue-600 flex items-center gap-1">
                        <div className="w-3 h-3 border border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                        Updating progress...
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <h3 className="text-xs font-semibold text-slate-500 mb-1">Assigned To</h3>
                <p className="text-sm text-slate-900">{task.assigned_to_first_name} {task.assigned_to_last_name}</p>
                <p className="text-xs text-slate-500">{task.assigned_to_email}</p>
              </div>
              <div>
                <h3 className="text-xs font-semibold text-slate-500 mb-1">Due Date</h3>
                <p className="text-sm text-slate-900">{formatDate(task.due_date)}</p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'comments' && (
          <div className="space-y-4">
            {!showCommentForm && (
              <button
                onClick={() => setShowCommentForm(true)}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 border-2 border-dashed border-slate-300 rounded-lg text-slate-600 hover:border-blue-500 hover:text-blue-600 transition-colors"
              >
                <MessageSquare className="w-4 h-4" />
                Add Comment
              </button>
            )}

            {showCommentForm && (
              <CommentForm
                taskId={task.id}
                onCancel={() => setShowCommentForm(false)}
                onCommentAdded={() => {
                  setShowCommentForm(false);
                  onTaskUpdate();
                }}
              />
            )}

            {task.comments?.length > 0 ? (
              <div className="space-y-3">
                {task.comments.map(comment => (
                  <div key={comment.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-full flex items-center justify-center text-white text-xs font-medium">
                          {comment.user_first_name[0]}{comment.user_last_name[0]}
                        </div>
                        <span className="text-sm font-medium text-slate-900">
                          {comment.user_first_name} {comment.user_last_name}
                        </span>
                      </div>
                      <span className="text-xs text-slate-500">{formatDate(comment.created_at)}</span>
                    </div>
                    <p className="text-sm text-slate-600 whitespace-pre-wrap">{comment.text}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <MessageSquare className="w-12 h-12 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-500">No comments yet</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'reports' && (
          <div className="space-y-3">
            {task.daily_reports?.length > 0 ? (
              task.daily_reports.map(report => (
                <div key={report.id} className="p-4 bg-slate-50 rounded-lg border border-slate-200">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-full flex items-center justify-center text-white text-xs font-medium">
                        {report.updated_by_first_name[0]}{report.updated_by_last_name[0]}
                      </div>
                      <span className="text-sm font-medium text-slate-900">
                        {report.updated_by_first_name} {report.updated_by_last_name}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500">{formatDate(report.date)}</span>
                  </div>

                  {report.completed_description && (
                    <div className="mb-2">
                      <h4 className="text-xs font-semibold text-emerald-700 mb-1">✓ Completed</h4>
                      <p className="text-sm text-slate-600">{report.completed_description}</p>
                    </div>
                  )}

                  {report.remaining_description && (
                    <div className="mb-2">
                      <h4 className="text-xs font-semibold text-blue-700 mb-1">→ Remaining</h4>
                      <p className="text-sm text-slate-600">{report.remaining_description}</p>
                    </div>
                  )}

                  {report.next_action_plan && (
                    <div>
                      <h4 className="text-xs font-semibold text-indigo-700 mb-1">⚡ Next Steps</h4>
                      <p className="text-sm text-slate-600">{report.next_action_plan}</p>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-8">
                <FileText className="w-12 h-12 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-500">No reports yet</p>
              </div>
            )}
          </div>
        )}
      </div>

      {showReportForm && (
        <DailyReportForm
          task={task}
          onClose={() => setShowReportForm(false)}
          onReportAdded={() => {
            setShowReportForm(false);
            onTaskUpdate();
          }}
        />
      )}
    </div>
  );
};

// Comment Form Component
const CommentForm = ({ taskId, onCommentAdded, onCancel }) => {
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
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <textarea
        className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type your comment..."
        rows="3"
        required
      />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={loading || !text.trim()}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium text-sm"
        >
          <Send className="w-4 h-4" />
          {loading ? 'Posting...' : 'Post'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-all font-medium text-sm"
        >
          Cancel
        </button>
      </div>
    </form>
  );
};

// Daily Report Form Component
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
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });

    // Recalculate days when dates change
    if (name === 'start_date' || name === 'due_date') {
      const newStartDate = name === 'start_date' ? value : formData.start_date;
      const newEndDate = name === 'due_date' ? value : formData.due_date;
      calculateDays(newStartDate, newEndDate);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Add Daily Report</h2>
              <p className="text-sm text-slate-500 mt-1">Track your progress for {task.title}</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-180px)]">
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Status</label>
            <select
              name="status"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">What was completed today?</label>
            <textarea
              name="completed_description"
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              value={formData.completed_description}
              onChange={handleChange}
              placeholder="Describe what you accomplished..."
              rows="3"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">What remains to be done?</label>
            <textarea
              name="remaining_description"
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              value={formData.remaining_description}
              onChange={handleChange}
              placeholder="Describe what still needs to be completed..."
              rows="3"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Reason for incompletion (if any)</label>
            <textarea
              name="reason_for_incompletion"
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              value={formData.reason_for_incompletion}
              onChange={handleChange}
              placeholder="Explain any blockers..."
              rows="2"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Next action plan</label>
            <textarea
              name="next_action_plan"
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              value={formData.next_action_plan}
              onChange={handleChange}
              placeholder="What are your plans for tomorrow?"
              rows="2"
            />
          </div>
        </form>

        <div className="p-6 border-t border-slate-200 bg-slate-50 flex gap-3">
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium"
          >
            {loading ? 'Submitting...' : 'Submit Report'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-6 py-3 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-all font-medium"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

// Create Task Modal Component
const CreateTaskModal = ({ onClose, onTaskCreated }) => {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    assigned_to_id: '',
    start_date: '',
    due_date: '',
    priority: 'medium',
    status: 'not_started'
  });
  const [loading, setLoading] = useState(false);
  const [calculatedDays, setCalculatedDays] = useState(null);
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await authAPI.getUsers();
        setUsers(response.data.results || []);
      } catch (error) {
        console.error('Error fetching users:', error);
      } finally {
        setUsersLoading(false);
      }
    };

    fetchUsers();
  }, []);

  const calculateDays = (startDate, endDate) => {
    if (!startDate || !endDate) {
      setCalculatedDays(null);
      return;
    }

    const start = new Date(startDate);
    const end = new Date(endDate);
    const diffTime = end - start;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays >= 0) {
      setCalculatedDays(diffDays);
    } else {
      setCalculatedDays(null);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });

    // Recalculate days when dates change
    if (name === 'start_date' || name === 'due_date') {
      const newStartDate = name === 'start_date' ? value : formData.start_date;
      const newEndDate = name === 'due_date' ? value : formData.due_date;
      calculateDays(newStartDate, newEndDate);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await taskAPI.createTask(formData);
      onTaskCreated();
    } catch (error) {
      console.error('Error creating task:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Create New Task</h2>
              <p className="text-sm text-slate-500 mt-1">Add a new task to the project</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-180px)]">
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Task Title *</label>
            <input
              type="text"
              name="title"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={formData.title}
              onChange={handleChange}
              placeholder="Enter task title..."
              required
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Description</label>
            <textarea
              name="description"
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              value={formData.description}
              onChange={handleChange}
              placeholder="Describe the task..."
              rows="3"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Assign To User *</label>
            <select
              name="assigned_to_id"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={formData.assigned_to_id}
              onChange={handleChange}
              required
              disabled={usersLoading}
            >
              <option value="">
                {usersLoading ? 'Loading users...' : 'Select a user'}
              </option>
              {users.map(user => (
                <option key={user.id} value={user.id}>
                  {user.first_name} {user.last_name} ({user.email}) - {user.role}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">Select a user from the authentication service</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Start Date</label>
              <input
                type="date"
                name="start_date"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.start_date}
                onChange={handleChange}
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Due Date</label>
              <input
                type="date"
                name="due_date"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.due_date}
                onChange={handleChange}
              />
            </div>
          </div>

          {calculatedDays !== null && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-blue-600" />
                <span className="text-sm font-medium text-blue-900">
                  Task Duration: {calculatedDays} day{calculatedDays !== 1 ? 's' : ''}
                </span>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Priority</label>
              <select
                name="priority"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.priority}
                onChange={handleChange}
              >
                <option value="low">Low Priority</option>
                <option value="medium">Medium Priority</option>
                <option value="high">High Priority</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Status</label>
              <select
                name="status"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.status}
                onChange={handleChange}
              >
                <option value="not_started">Not Started</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="blocked">Blocked</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Progress Percentage</label>
            <input
              type="number"
              name="progress_percentage"
              min="0"
              max="100"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={formData.progress_percentage}
              onChange={handleChange}
              placeholder="Enter progress percentage (0-100)"
            />
            <p className="text-xs text-slate-500 mt-1">Enter a value between 0 and 100</p>
          </div>
        </form>

        <div className="p-6 border-t border-slate-200 bg-slate-50 flex gap-3">
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium"
          >
            {loading ? 'Creating...' : 'Create Task'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-6 py-3 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-all font-medium"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

// Edit Task Modal Component
const EditTaskModal = ({ task, currentUser, onClose, onTaskUpdated }) => {
  const [formData, setFormData] = useState({
    title: task.title || '',
    description: task.description || '',
    assigned_to_id: task.assigned_to_id || '',
    assigned_by_id: currentUser.id,
    start_date: task.start_date ? task.start_date.split('T')[0] : '',
    due_date: task.due_date ? task.due_date.split('T')[0] : '',
    priority: task.priority || 'medium',
    status: task.status || 'not_started',
    progress_percentage: task.progress_percentage || 0
  });
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await authAPI.getUsers();
        setUsers(response.data.results || []);
      } catch (error) {
        console.error('Error fetching users:', error);
      } finally {
        setUsersLoading(false);
      }
    };

    fetchUsers();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await taskAPI.updateTask(task.id, formData);
      onTaskUpdated();
    } catch (error) {
      console.error('Error updating task:', error);
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
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Edit Task</h2>
              <p className="text-sm text-slate-500 mt-1">Update task details</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-180px)]">
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Task Title *</label>
            <input
              type="text"
              name="title"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={formData.title}
              onChange={handleChange}
              placeholder="Enter task title..."
              required
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Description</label>
            <textarea
              name="description"
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              value={formData.description}
              onChange={handleChange}
              placeholder="Describe the task..."
              rows="3"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Assign To User *</label>
            <select
              name="assigned_to_id"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={formData.assigned_to_id}
              onChange={handleChange}
              required
              disabled={usersLoading}
            >
              <option value="">
                {usersLoading ? 'Loading users...' : 'Select a user'}
              </option>
              {users.map(user => (
                <option key={user.id} value={user.id}>
                  {user.first_name} {user.last_name} ({user.email}) - {user.role}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">Select a user from the authentication service</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Start Date</label>
              <input
                type="date"
                name="start_date"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.start_date}
                onChange={handleChange}
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Due Date</label>
              <input
                type="date"
                name="due_date"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.due_date}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Priority</label>
              <select
                name="priority"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.priority}
                onChange={handleChange}
              >
                <option value="low">Low Priority</option>
                <option value="medium">Medium Priority</option>
                <option value="high">High Priority</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Status</label>
              <select
                name="status"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.status}
                onChange={handleChange}
              >
                <option value="not_started">Not Started</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="blocked">Blocked</option>
              </select>
            </div>
          </div>
        </form>

        <div className="p-6 border-t border-slate-200 bg-slate-50 flex gap-3">
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium"
          >
            {loading ? 'Updating...' : 'Update Task'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-6 py-3 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-all font-medium"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
